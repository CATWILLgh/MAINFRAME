package main

import (
	"errors"
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type releaseLoader func(string) (releasecontract.Release, error)

type previewServiceBuilder func(
	string,
	releasecontract.Release,
	string,
	codexstate.Client,
	hostApplicationDiscoverer,
) (lifecycle.Service, error)

type releaseSnapshotBuilder struct {
	releaseRoot string
	cwd         string
	load        releaseLoader
	client      func() codexstate.Client
	build       previewServiceBuilder
	discover    hostApplicationDiscoverer
}

func newReleaseSnapshotBuilder(releaseRoot, cwd string) releaseSnapshotBuilder {
	return releaseSnapshotBuilder{
		releaseRoot: releaseRoot,
		cwd:         cwd,
		load:        releasecontract.Load,
		client:      func() codexstate.Client { return codexstate.NewAppServerClient() },
		build:       buildPreviewServiceFromContextWithHostDiscovery,
		discover:    hostcompatibility.DiscoverApplications,
	}
}

func (builder releaseSnapshotBuilder) Build() (application.Snapshot, error) {
	if err := builder.validate(); err != nil {
		return application.Snapshot{}, err
	}
	release, err := builder.load(builder.releaseRoot)
	if err != nil {
		return application.Snapshot{}, fmt.Errorf("load release: %w", err)
	}
	service, err := builder.build(
		builder.releaseRoot,
		release,
		builder.cwd,
		builder.client(),
		builder.discover,
	)
	if err != nil {
		return application.Snapshot{}, err
	}
	return application.Snapshot{
		Release: executor.ReleaseIdentity{
			ID:          release.ID,
			IndexSHA256: release.IndexSHA256,
		},
		Lifecycle: service,
	}, nil
}

func (builder releaseSnapshotBuilder) validate() error {
	if builder.releaseRoot == "" || builder.cwd == "" {
		return errors.New("release snapshot paths must not be empty")
	}
	if builder.load == nil || builder.client == nil ||
		builder.build == nil || builder.discover == nil {
		return errors.New("release snapshot dependencies must not be nil")
	}
	return nil
}

type productionApplyExecutorFactory struct {
	releaseRoot string
	environment hostlayout.Environment
}

func (factory productionApplyExecutorFactory) Open(
	refresher executor.Refresher,
) (application.ApplySession, error) {
	layout, err := hostlayout.Resolve(factory.environment, factory.releaseRoot)
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
	runner := executor.NewWithConfiguration(
		state,
		state,
		refresher,
		workspace,
		workspace,
	)
	return &productionApplySession{executor: runner, state: state}, nil
}

type productionApplySession struct {
	executor executor.Executor
	state    *executor.UnixState
}

func (session *productionApplySession) Apply(
	preview executor.Preview,
) (executor.Result, error) {
	return session.executor.Apply(preview)
}

func (session *productionApplySession) Close() error {
	return session.state.Close()
}

func buildApplyService() (application.Service, error) {
	releaseRoot, err := resolveReleaseRoot()
	if err != nil {
		return application.Service{}, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return application.Service{}, fmt.Errorf("resolve working directory: %w", err)
	}
	builder := newReleaseSnapshotBuilder(releaseRoot, cwd)
	factory := productionApplyExecutorFactory{
		releaseRoot: releaseRoot,
		environment: hostEnvironment(),
	}
	service, err := application.New(builder, factory)
	if err != nil {
		return application.Service{}, fmt.Errorf("build apply service: %w", err)
	}
	return service, nil
}
