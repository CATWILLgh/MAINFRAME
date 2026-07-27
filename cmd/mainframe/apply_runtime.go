package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type releaseLoader func(string) (releasecontract.Release, error)

type releaseRootResolver func() (string, error)

type releaseRootSource struct {
	mu      sync.Mutex
	resolve releaseRootResolver
	value   string
}

func (source *releaseRootSource) Resolve() (string, error) {
	source.mu.Lock()
	defer source.mu.Unlock()
	if source.value != "" {
		return source.value, nil
	}
	if source.resolve == nil {
		return "", errors.New("release root resolver must not be nil")
	}
	value, err := source.resolve()
	if err != nil {
		return "", err
	}
	source.value = value
	return value, nil
}

type previewServiceBuilder func(
	string,
	releasecontract.Release,
	string,
	codexstate.Client,
	diagnosticsObservationScope,
	hostApplicationDiscoverer,
) (lifecycle.Service, error)

type credentialSnapshotLoader func(
	string,
	releasecontract.Release,
) (credentialRuntimeState, error)

type releaseSnapshotBuilder struct {
	resolveRoot     releaseRootResolver
	expectedRelease *executor.ReleaseIdentity
	cwd             string
	load            releaseLoader
	client          func() codexstate.Client
	build           previewServiceBuilder
	discover        hostApplicationDiscoverer
	loadCredentials credentialSnapshotLoader
}

func newReleaseSnapshotBuilder(releaseRoot, cwd string) releaseSnapshotBuilder {
	return newReleaseSnapshotBuilderWithResolver(
		func() (string, error) { return releaseRoot, nil },
		cwd,
	)
}

func newReleaseSnapshotBuilderWithResolver(
	resolveRoot releaseRootResolver,
	cwd string,
) releaseSnapshotBuilder {
	return releaseSnapshotBuilder{
		resolveRoot:     resolveRoot,
		cwd:             cwd,
		load:            releasecontract.Load,
		client:          func() codexstate.Client { return codexstate.NewAppServerClient() },
		build:           buildPreviewServiceFromContextWithObservation,
		discover:        hostcompatibility.DiscoverApplications,
		loadCredentials: loadCredentialRuntime,
	}
}

func (builder releaseSnapshotBuilder) Build(
	request application.Request,
) (application.Snapshot, error) {
	if err := builder.validate(); err != nil {
		return application.Snapshot{}, err
	}
	releaseRoot, err := builder.resolveRoot()
	if err != nil {
		return application.Snapshot{}, err
	}
	if releaseRoot == "" {
		return application.Snapshot{}, errors.New("release root must not be empty")
	}
	release, err := builder.load(releaseRoot)
	if err != nil {
		return application.Snapshot{}, fmt.Errorf("load release: %w", err)
	}
	identity := executor.ReleaseIdentity{
		ID:          release.ID,
		IndexSHA256: release.IndexSHA256,
	}
	if builder.expectedRelease != nil && identity != *builder.expectedRelease {
		return application.Snapshot{}, fmt.Errorf(
			"release identity changed during the session",
		)
	}
	service, err := builder.build(
		releaseRoot,
		release,
		builder.cwd,
		builder.client(),
		diagnosticsObservationScopeFor(request),
		builder.discover,
	)
	if err != nil {
		return application.Snapshot{}, err
	}
	snapshot := application.Snapshot{
		Release:   identity,
		Lifecycle: service,
	}
	if request.CredentialInstances != nil || len(request.MCPCredentials) > 0 {
		if builder.loadCredentials == nil {
			return application.Snapshot{}, errors.New(
				"credential snapshot loader must not be nil",
			)
		}
		credentials, err := builder.loadCredentials(releaseRoot, release)
		if err != nil {
			return application.Snapshot{}, err
		}
		credentialSnapshot := credentials.snapshot
		snapshot.Credentials = &credentialSnapshot
	}
	return snapshot, nil
}

func (builder releaseSnapshotBuilder) validate() error {
	if builder.cwd == "" {
		return errors.New("release snapshot working directory must not be empty")
	}
	if builder.resolveRoot == nil || builder.load == nil || builder.client == nil ||
		builder.build == nil || builder.discover == nil {
		return errors.New("release snapshot dependencies must not be nil")
	}
	return nil
}

type productionApplyExecutorFactory struct {
	resolveRoot releaseRootResolver
	environment hostlayout.Environment
}

func (factory productionApplyExecutorFactory) Open(
	refresher executor.Refresher,
) (application.ApplySession, error) {
	if factory.resolveRoot == nil {
		return nil, errors.New("release root resolver must not be nil")
	}
	releaseRoot, err := factory.resolveRoot()
	if err != nil {
		return nil, err
	}
	layout, err := hostlayout.Resolve(factory.environment, releaseRoot)
	if err != nil {
		return nil, fmt.Errorf("resolve host layout: %w", err)
	}
	workspace, err := linkworkspace.New(layout.Source(), layout.Targets())
	if err != nil {
		return nil, fmt.Errorf("open installation workspace: %w", err)
	}
	state, err := executor.OpenUnixState(layout.State())
	if err != nil {
		return nil, fmt.Errorf("open transaction state: %w", err)
	}
	secretHelper := filepath.Join(
		layout.Targets()[domain.RootUserBin],
		"secret",
	)
	runner := executor.NewWithConfigurationAndSecrets(
		state,
		state,
		refresher,
		workspace,
		workspace,
		newSecretHelperResolver(secretHelper),
	)
	return &productionExecutorSession{executor: runner, state: state}, nil
}

type productionExecutorSession struct {
	executor executor.Executor
	state    *executor.UnixState
}

func (session *productionExecutorSession) Apply(
	preview executor.Preview,
) (executor.Result, error) {
	return session.executor.Apply(preview)
}

func (session *productionExecutorSession) ApplyWithoutRecovery(
	preview executor.Preview,
) (executor.Result, error) {
	return session.executor.ApplyWithoutRecovery(preview)
}

func (session *productionExecutorSession) Recover() (executor.Result, error) {
	return session.executor.Recover()
}

func (session *productionExecutorSession) Close() error {
	return session.state.Close()
}

func buildApplyService() (application.Service, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return application.Service{}, fmt.Errorf("resolve working directory: %w", err)
	}
	releaseRoots := &releaseRootSource{resolve: resolveReleaseRoot}
	return buildApplyServiceWithSource(releaseRoots, cwd, nil)
}

func buildPinnedApplyService(
	releaseRoot string,
	cwd string,
	expected executor.ReleaseIdentity,
) (application.Service, error) {
	if releaseRoot == "" {
		return application.Service{}, errors.New("release root must not be empty")
	}
	releaseRoots := &releaseRootSource{value: releaseRoot}
	return buildApplyServiceWithSource(releaseRoots, cwd, &expected)
}

func buildApplyServiceWithSource(
	releaseRoots *releaseRootSource,
	cwd string,
	expected *executor.ReleaseIdentity,
) (application.Service, error) {
	recoveryFactory, err := newProductionRecoveryExecutorFactory()
	if err != nil {
		return application.Service{}, err
	}
	builder := newReleaseSnapshotBuilderWithResolver(releaseRoots.Resolve, cwd)
	if expected != nil {
		identity := *expected
		builder.expectedRelease = &identity
	}
	factory := productionApplyExecutorFactory{
		resolveRoot: releaseRoots.Resolve,
		environment: hostEnvironment(),
	}
	service, err := application.New(builder, factory, recoveryFactory)
	if err != nil {
		return application.Service{}, fmt.Errorf("build apply service: %w", err)
	}
	return service, nil
}
