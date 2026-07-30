//go:build unix

package main

import (
	"errors"
	"fmt"
	"io"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/secretstore"
)

type secretRetirementInspection struct {
	scope      secretRetirementScope
	store      *secretstore.Store
	instances  credentialcatalog.Instances
	references []mcpconfiguration.ManagedSecretReference
}

func runSecretRetirementPrepareCommand(
	name string,
	output, errorOutput io.Writer,
) int {
	response, err := reviewSecretRetirement(name)
	if err != nil {
		fmt.Fprintf(errorOutput, "credentials secret-retire prepare: %v\n", err)
		return 1
	}
	if err := encodeCredentialResponse(output, response); err != nil {
		fmt.Fprintf(errorOutput, "credentials secret-retire prepare: %v\n", err)
		return 1
	}
	return 0
}

func runSecretRetirementApplyCommand(
	confirmation string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	if !credentialConfirmationPattern.MatchString(confirmation) {
		fmt.Fprintln(
			errorOutput,
			"credentials secret-retire apply: confirmation digest is invalid",
		)
		return 2
	}
	request, err := decodeSecretRetirementApplyRequest(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials secret-retire apply: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := executeSecretRetirement(request, confirmation)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials secret-retire apply: %v\n",
			publicSecretRetirementError(err),
		)
		return 1
	}
	if err := encodeCredentialResponse(output, response); err != nil {
		fmt.Fprintf(errorOutput, "credentials secret-retire apply: %v\n", err)
		return 1
	}
	return 0
}

func reviewSecretRetirement(
	name string,
) (secretRetirementReviewResponse, error) {
	inspection, err := inspectSecretRetirementState()
	if err != nil {
		return secretRetirementReviewResponse{}, err
	}
	if err := requireSecretRetirementUnused(name, inspection); err != nil {
		return secretRetirementReviewResponse{}, err
	}
	generation, err := inspection.store.PrepareRetire(name)
	if err != nil {
		return secretRetirementReviewResponse{}, publicSecretRetirementError(err)
	}
	request := secretRetirementApplyRequest{
		SchemaVersion: secretRetirementProtocolVersion,
		Kind:          secretRetirementApplyKind,
		Secret: credentialSecretReference{
			Backend: string(credentialcatalog.BackendSecretEnvironment),
			Name:    name,
		},
		ExpectedGeneration: generation,
	}
	commitment, err := secretRetirementCommitment(request, inspection.scope)
	if err != nil {
		return secretRetirementReviewResponse{}, err
	}
	return secretRetirementReviewResponse{
		SchemaVersion:  secretRetirementProtocolVersion,
		Kind:           secretRetirementReviewKind,
		ApplyRequest:   request,
		ExpectedReview: commitment,
	}, nil
}

func executeSecretRetirement(
	request secretRetirementApplyRequest,
	confirmation string,
) (secretRetirementApplyResponse, error) {
	state, lock, err := acquireSecretRetirementTransactionLock()
	if err != nil {
		return secretRetirementApplyResponse{}, err
	}
	defer state.Close()
	defer lock.Unlock()
	inspection, err := inspectSecretRetirementState()
	if err != nil {
		return secretRetirementApplyResponse{}, err
	}
	if err := requireSecretRetirementUnused(
		request.Secret.Name,
		inspection,
	); err != nil {
		return secretRetirementApplyResponse{}, err
	}
	current, err := secretRetirementCommitment(request, inspection.scope)
	if err != nil {
		return secretRetirementApplyResponse{}, err
	}
	if !secretRetirementCommitmentsEqual(current, confirmation) {
		return secretRetirementApplyResponse{}, errors.New(
			"review confirmation is stale; run prepare again",
		)
	}
	if err := inspection.store.DeleteIfGeneration(
		request.Secret.Name,
		request.ExpectedGeneration,
	); err != nil {
		return secretRetirementApplyResponse{}, publicSecretRetirementError(err)
	}
	return secretRetirementApplyResponse{
		SchemaVersion: secretRetirementProtocolVersion,
		Kind:          secretRetirementResultKind,
		Applied:       true,
		Warnings: []string{
			"Provider-side credentials were not revoked.",
			"Existing process environments were not changed.",
		},
	}, nil
}

func inspectSecretRetirementState() (secretRetirementInspection, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return secretRetirementInspection{}, err
	}
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		snapshot.release.MCPCatalog,
	)
	if err != nil {
		return secretRetirementInspection{}, errCredentialDefinitions
	}
	instances, err := loadCredentialInstances(snapshot, definitions)
	if err != nil {
		return secretRetirementInspection{}, err
	}
	layout, err := hostlayout.Resolve(hostEnvironment(), snapshot.root)
	if err != nil {
		return secretRetirementInspection{}, errCredentialLocation
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return secretRetirementInspection{}, errCredentialLocation
	}
	references, err := mcpconfiguration.ScanManagedSecretReferences(namespace)
	if err != nil {
		return secretRetirementInspection{}, err
	}
	targets := layout.Targets()
	store := secretstore.New(targets[domain.RootCredentialsConfig])
	return secretRetirementInspection{
		scope: secretRetirementScope{
			ReleaseRoot: snapshot.root, TransactionState: layout.State(),
			CredentialRoot:  targets[domain.RootCredentialsConfig],
			SecretStorePath: store.Path(),
			HomeRoot:        targets[domain.RootHome],
			ClaudeRoot:      targets[domain.RootClaudeConfig],
			CodexRoot:       targets[domain.RootCodexConfig],
			OpenCodeRoot:    targets[domain.RootOpenCodeConfig],
			AntigravityRoot: targets[domain.RootAntigravityData],
		},
		store: store, instances: instances, references: references,
	}, nil
}

func requireSecretRetirementUnused(
	name string,
	inspection secretRetirementInspection,
) error {
	reference := credentialcatalog.SecretReference{
		Backend: credentialcatalog.BackendSecretEnvironment,
		Name:    name,
	}
	if credentialcatalog.ValidateSecretReference(reference) != nil {
		return errors.New("secret reference is invalid")
	}
	if len(inspection.instances.Uses(reference)) != 0 {
		return errors.New("secret is still referenced by the credential catalog")
	}
	for _, managed := range inspection.references {
		if managed.Reference == name {
			return fmt.Errorf(
				"secret is still referenced by a managed adapter registry",
			)
		}
	}
	return nil
}

func acquireSecretRetirementTransactionLock() (
	*executor.UnixState,
	executor.Lock,
	error,
) {
	root, err := resolveReleaseRoot()
	if err != nil {
		return nil, nil, err
	}
	layout, err := hostlayout.Resolve(hostEnvironment(), root)
	if err != nil {
		return nil, nil, errCredentialLocation
	}
	state, err := executor.OpenUnixState(filepath.Clean(layout.State()))
	if err != nil {
		return nil, nil, fmt.Errorf("open transaction state: %w", err)
	}
	lock, err := state.Lock()
	if err != nil {
		state.Close()
		return nil, nil, err
	}
	return state, lock, nil
}

func publicSecretRetirementError(err error) error {
	switch {
	case errors.Is(err, secretstore.ErrNotFound):
		return errors.New("secret store has no entry for the requested name")
	case errors.Is(err, secretstore.ErrGenerationChanged):
		return errors.New("secret store changed after retirement was prepared")
	case errors.Is(err, secretstore.ErrInvalidInput):
		return errors.New("secret reference or generation is invalid")
	case errors.Is(err, secretstore.ErrUnsafeStore):
		return errors.New("credential store is unsafe")
	default:
		return err
	}
}
