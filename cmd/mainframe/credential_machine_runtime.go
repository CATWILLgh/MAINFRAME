package main

import (
	"errors"
	"fmt"
	"path/filepath"
	"sync"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type credentialObservation struct {
	release     executor.ReleaseIdentity
	credentials credentialcatalog.InstanceSnapshot
}

type credentialObserver func() (credentialObservation, error)

type credentialOnlySnapshotBuilder struct {
	mu        sync.Mutex
	expected  executor.ReleaseIdentity
	lifecycle lifecycle.Service
	first     *credentialObservation
	observe   credentialObserver
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
	credentials := observation.credentials
	return application.Snapshot{
		Release:     observation.release,
		Lifecycle:   builder.lifecycle,
		Credentials: &credentials,
	}, nil
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
	service, err := buildApplyServiceWithSnapshotBuilder(roots, builder)
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
		release:     releaseIdentity(release),
		credentials: runtime.snapshot,
	}, nil
}

func releaseIdentity(release releasecontract.Release) executor.ReleaseIdentity {
	return executor.ReleaseIdentity{
		ID: release.ID, IndexSHA256: release.IndexSHA256,
	}
}
