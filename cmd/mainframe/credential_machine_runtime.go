package main

import (
	"errors"
	"fmt"
	"path/filepath"
	"sync"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type credentialObservation struct {
	release           executor.ReleaseIdentity
	credentials       credentialcatalog.InstanceSnapshot
	managedReferences func() (
		[]mcpconfiguration.ManagedSecretReference,
		error,
	)
}

type credentialObserver func() (credentialObservation, error)

type credentialOnlySnapshotBuilder struct {
	mu        sync.Mutex
	expected  executor.ReleaseIdentity
	lifecycle lifecycle.Service
	first     *credentialObservation
	observe   credentialObserver
}

type legacyCredentialSnapshotBuilder struct {
	mu       sync.Mutex
	base     application.SnapshotBuilder
	validate func() error
	builds   int
}

type credentialMachineSession struct {
	definitions credentialcatalog.Definitions
	current     credentialcatalog.Instances
	service     application.Service
	scope       credentialCommitmentScope
}

func (builder *credentialOnlySnapshotBuilder) Build(
	request application.Request,
) (application.Snapshot, error) {
	if err := validateCredentialOnlyRequest(request); err != nil {
		return application.Snapshot{}, err
	}
	observation, err := builder.nextObservation()
	if err != nil {
		return application.Snapshot{}, err
	}
	if observation.release != builder.expected {
		return application.Snapshot{}, errors.New(
			"release identity changed after credential review",
		)
	}
	if err := validateManagedCredentialDeletion(
		request,
		observation.credentials,
		observation.managedReferences,
	); err != nil {
		return application.Snapshot{}, err
	}
	credentials := observation.credentials
	return application.Snapshot{
		Release:     observation.release,
		Lifecycle:   builder.lifecycle,
		Credentials: &credentials,
	}, nil
}

func validateManagedCredentialDeletion(
	request application.Request,
	current credentialcatalog.InstanceSnapshot,
	observeManaged func() ([]mcpconfiguration.ManagedSecretReference, error),
) error {
	changes, err := credentialcatalog.PlanInstanceChanges(
		current.Instances(),
		*request.CredentialInstances,
	)
	if err != nil {
		return err
	}
	deletedReferences := make(map[string]struct{})
	for _, change := range changes {
		if change.Kind != credentialcatalog.ChangeDelete {
			continue
		}
		for _, binding := range change.Before.Credentials {
			deletedReferences[binding.Secret.Name] = struct{}{}
		}
	}
	if len(deletedReferences) == 0 {
		return nil
	}
	managed, err := observeManaged()
	if err != nil {
		return err
	}
	for _, reference := range managed {
		if _, blocked := deletedReferences[reference.Reference]; blocked {
			return fmt.Errorf(
				"credential secret %q remains in managed adapter registry %s/%s",
				reference.Reference,
				reference.ComponentID,
				reference.ResourceID,
			)
		}
	}
	return nil
}

func (builder *credentialOnlySnapshotBuilder) nextObservation() (
	credentialObservation,
	error,
) {
	builder.mu.Lock()
	defer builder.mu.Unlock()
	if builder.first != nil {
		observation := *builder.first
		builder.first = nil
		return observation, nil
	}
	if builder.observe == nil {
		return credentialObservation{}, errors.New(
			"credential observer must not be nil",
		)
	}
	observation, err := builder.observe()
	if err != nil {
		return credentialObservation{}, fmt.Errorf(
			"observe credential state: %w",
			err,
		)
	}
	return observation, nil
}

func (builder *legacyCredentialSnapshotBuilder) Build(
	request application.Request,
) (application.Snapshot, error) {
	builder.mu.Lock()
	builder.builds++
	requiresValidation := builder.builds > 1
	builder.mu.Unlock()
	if requiresValidation {
		if err := builder.validate(); err != nil {
			return application.Snapshot{}, fmt.Errorf(
				"validate legacy credential sources: %w",
				err,
			)
		}
	}
	return builder.base.Build(request)
}

func validateCredentialOnlyRequest(request application.Request) error {
	if request.CredentialInstances == nil ||
		len(request.Components) != 0 ||
		len(request.MCPSelections) != 0 ||
		len(request.MCPCredentials) != 0 ||
		request.Diagnostics != (diagnostics.Desired{}) {
		return errors.New(
			"machine credential review accepts only credential metadata",
		)
	}
	return nil
}

func buildCredentialMachineSession() (credentialMachineSession, error) {
	return buildCredentialMachineSessionWithLegacyValidation("")
}

func buildLegacyCredentialMachineSession(
	expectedSourceCommitment string,
) (credentialMachineSession, error) {
	if !credentialConfirmationPattern.MatchString(expectedSourceCommitment) {
		return credentialMachineSession{}, errors.New(
			"legacy source commitment is invalid",
		)
	}
	return buildCredentialMachineSessionWithLegacyValidation(
		expectedSourceCommitment,
	)
}

func buildCredentialMachineSessionWithLegacyValidation(
	expectedSourceCommitment string,
) (credentialMachineSession, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return credentialMachineSession{}, err
	}
	runtime, err := loadCredentialRuntime(snapshot.root, snapshot.release)
	if err != nil {
		return credentialMachineSession{}, err
	}
	identity := releaseIdentity(snapshot.release)
	layout, err := hostlayout.Resolve(hostEnvironment(), snapshot.root)
	if err != nil {
		return credentialMachineSession{}, errCredentialLocation
	}
	neutral, err := lifecycle.New(snapshot.release.Model, domain.ObservedState{})
	if err != nil {
		return credentialMachineSession{}, fmt.Errorf(
			"build credential-only lifecycle: %w",
			err,
		)
	}
	first := credentialObservation{
		release: identity, credentials: runtime.snapshot,
		managedReferences: runtime.managedReferences,
	}
	builder := &credentialOnlySnapshotBuilder{
		expected:  identity,
		lifecycle: neutral,
		first:     &first,
		observe: func() (credentialObservation, error) {
			return observeCredentialState(snapshot.root)
		},
	}
	roots := &releaseRootSource{value: snapshot.root}
	var snapshotBuilder application.SnapshotBuilder = builder
	if expectedSourceCommitment != "" {
		snapshotBuilder = &legacyCredentialSnapshotBuilder{
			base: builder,
			validate: func() error {
				return validateLegacyCredentialSourceCommitment(
					snapshot.release,
					snapshot.root,
					expectedSourceCommitment,
				)
			},
		}
	}
	service, err := buildApplyServiceWithSnapshotBuilder(roots, snapshotBuilder)
	if err != nil {
		return credentialMachineSession{}, err
	}
	return credentialMachineSession{
		definitions: runtime.definitions,
		current:     runtime.snapshot.Instances(),
		service:     service,
		scope: credentialCommitmentScope{
			CredentialTarget: filepath.Join(
				layout.Targets()[domain.RootCredentialsConfig],
				string(credentialcatalog.UserInstancesPath),
			),
			TransactionState: layout.State(),
			ReleaseRoot:      snapshot.root,
		},
	}, nil
}

func validateLegacyCredentialSourceCommitment(
	release releasecontract.Release,
	root string,
	expected string,
) error {
	plan, err := inspectLegacyCredentialTransferPlan(
		release,
		root,
		hostEnvironment(),
	)
	if err != nil {
		return err
	}
	current, err := credentialmigration.LegacyTransferSourceCommitment(plan)
	if err != nil {
		return err
	}
	if !credentialCommitmentsEqual(current, expected) {
		return errors.New(
			"legacy credential sources changed after review",
		)
	}
	return nil
}

func observeCredentialState(root string) (credentialObservation, error) {
	release, err := releasecontract.Load(root)
	if err != nil {
		return credentialObservation{}, fmt.Errorf("load release: %w", err)
	}
	runtime, err := loadCredentialRuntime(root, release)
	if err != nil {
		return credentialObservation{}, err
	}
	return credentialObservation{
		release:           releaseIdentity(release),
		credentials:       runtime.snapshot,
		managedReferences: runtime.managedReferences,
	}, nil
}

func releaseIdentity(release releasecontract.Release) executor.ReleaseIdentity {
	return executor.ReleaseIdentity{
		ID: release.ID, IndexSHA256: release.IndexSHA256,
	}
}
