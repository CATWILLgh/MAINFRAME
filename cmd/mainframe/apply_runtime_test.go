package main

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestReleaseSnapshotBuilderReloadsAndReinspectsEveryBuild(t *testing.T) {
	releaseRoot := t.TempDir()
	loads := 0
	builds := 0
	clients := 0
	builder := releaseSnapshotBuilder{
		resolveRoot: func() (string, error) { return releaseRoot, nil },
		cwd:         t.TempDir(),
		load: func(root string) (releasecontract.Release, error) {
			loads++
			if root != releaseRoot {
				t.Fatalf("load root = %q, want %q", root, releaseRoot)
			}
			return releasecontract.Release{
				ID:          "release-" + string(rune('0'+loads)),
				IndexSHA256: applyRuntimeDigest(loads),
				Model:       previewOwnershipModel(t),
			}, nil
		},
		client: func() codexstate.Client {
			clients++
			return nil
		},
		build: func(
			_ string,
			release releasecontract.Release,
			_ string,
			_ codexstate.Client,
			_ hostApplicationDiscoverer,
		) (lifecycle.Service, error) {
			builds++
			return lifecycle.New(release.Model, domain.ObservedState{})
		},
		discover: hostcompatibility.DiscoverApplications,
	}

	first, err := builder.Build()
	if err != nil {
		t.Fatalf("first Build() error = %v", err)
	}
	second, err := builder.Build()
	if err != nil {
		t.Fatalf("second Build() error = %v", err)
	}

	if loads != 2 || builds != 2 || clients != 2 {
		t.Fatalf("loads/builds/clients = %d/%d/%d, want 2/2/2", loads, builds, clients)
	}
	if first.Release == second.Release {
		t.Fatalf("release identity was reused: %#v", first.Release)
	}
}

func TestProductionApplyExecutorFactoryCreatesStateOnlyWhenOpened(t *testing.T) {
	home := canonicalTempDir(t)
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	releaseRoot := canonicalTempDir(t)
	environment := hostlayout.Environment{
		LookupEnv: func(name string) (string, bool) {
			if name == "XDG_STATE_HOME" {
				return stateBase, true
			}
			return "", false
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "darwin",
	}
	factory := productionApplyExecutorFactory{
		resolveRoot: func() (string, error) { return releaseRoot, nil },
		environment: environment,
	}
	stateRoot := filepath.Join(stateBase, "mainframe")
	if _, err := os.Stat(stateRoot); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("state root exists before Open(): %v", err)
	}

	session, err := factory.Open(staticRefresher{})
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	if metadata, err := os.Stat(stateRoot); err != nil || !metadata.IsDir() {
		t.Fatalf("state root after Open() = %#v, %v", metadata, err)
	}
	if err := session.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}
}

func TestBuildApplyServiceDoesNotCreateState(t *testing.T) {
	home := t.TempDir()
	stateBase := filepath.Join(t.TempDir(), "state")
	t.Setenv("HOME", home)
	t.Setenv("XDG_STATE_HOME", stateBase)
	t.Setenv(releaseRootEnvironment, t.TempDir())

	if _, err := buildApplyService(); err != nil {
		t.Fatalf("buildApplyService() error = %v", err)
	}
	if _, err := os.Stat(filepath.Join(stateBase, "mainframe")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("building apply service created state: %v", err)
	}
}

func TestBuildApplyServiceDefersReleaseResolution(t *testing.T) {
	home := t.TempDir()
	stateBase := filepath.Join(t.TempDir(), "state")
	t.Setenv("HOME", home)
	t.Setenv("XDG_STATE_HOME", stateBase)
	t.Setenv(releaseRootEnvironment, filepath.Join(t.TempDir(), "missing"))

	if _, err := buildApplyService(); err != nil {
		t.Fatalf("buildApplyService() error = %v", err)
	}
	if _, err := os.Stat(filepath.Join(stateBase, "mainframe")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("building apply service created state: %v", err)
	}
}

func TestProductionApplyRecoversJournalBeforeOpeningDeletedRelease(t *testing.T) {
	home := canonicalTempDir(t)
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	releaseRoot := canonicalTempDir(t)
	environment := hostlayout.Environment{
		LookupEnv: func(name string) (string, bool) {
			if name == "XDG_STATE_HOME" {
				return stateBase, true
			}
			return "", false
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "darwin",
	}
	releaseRoots := &releaseRootSource{
		resolve: func() (string, error) { return releaseRoot, nil },
	}
	layout, err := hostlayout.ResolveRecovery(environment)
	if err != nil {
		t.Fatalf("ResolveRecovery() error = %v", err)
	}
	service, err := application.New(
		productionTestSnapshotBuilder(t, releaseRoots.Resolve),
		productionApplyExecutorFactory{
			resolveRoot: releaseRoots.Resolve,
			environment: environment,
		},
		productionRecoveryExecutorFactory{layout: layout},
	)
	if err != nil {
		t.Fatalf("application.New() error = %v", err)
	}
	reviewed, err := service.Review(application.Request{
		Components: []domain.ComponentID{domain.ComponentCodex},
	})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	stateRoot := filepath.Join(stateBase, "mainframe")
	saveEmptyProductionJournal(t, stateRoot)
	if err := os.RemoveAll(releaseRoot); err != nil {
		t.Fatalf("remove release: %v", err)
	}

	if _, err := service.Apply(reviewed); err == nil ||
		!strings.Contains(err.Error(), "pin source root") {
		t.Fatalf("Apply() error = %v", err)
	}
	assertProductionJournalMissing(t, stateRoot)
}

func productionTestSnapshotBuilder(
	t *testing.T,
	resolve releaseRootResolver,
) releaseSnapshotBuilder {
	t.Helper()
	return releaseSnapshotBuilder{
		resolveRoot: resolve,
		cwd:         t.TempDir(),
		load: func(string) (releasecontract.Release, error) {
			return releasecontract.Release{
				ID:          "release",
				IndexSHA256: applyRuntimeDigest(1),
				Model:       previewOwnershipModel(t),
			}, nil
		},
		client: func() codexstate.Client { return nil },
		build: func(
			_ string,
			release releasecontract.Release,
			_ string,
			_ codexstate.Client,
			_ hostApplicationDiscoverer,
		) (lifecycle.Service, error) {
			return lifecycle.New(release.Model, domain.ObservedState{})
		},
		discover: hostcompatibility.DiscoverApplications,
	}
}

func saveEmptyProductionJournal(t *testing.T, stateRoot string) {
	t.Helper()
	state, err := executor.OpenUnixState(stateRoot)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	journal := executor.Journal{
		SchemaVersion: executor.CurrentJournalSchemaVersion,
		Release: executor.ReleaseIdentity{
			ID:          "release",
			IndexSHA256: applyRuntimeDigest(1),
		},
		Desired: []domain.ComponentID{domain.ComponentCodex},
		Status:  executor.TransactionInProgress,
	}
	if err := state.Save(journal); err != nil {
		state.Close()
		t.Fatalf("Save() error = %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}
}

func assertProductionJournalMissing(t *testing.T, stateRoot string) {
	t.Helper()
	state, err := executor.OpenUnixState(stateRoot)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	defer state.Close()
	journal, err := state.Load()
	if err != nil || journal != nil {
		t.Fatalf("Load() after recovery = %#v, %v", journal, err)
	}
}

type staticRefresher struct{}

func (staticRefresher) Refresh(desired []domain.ComponentID) (executor.Preview, error) {
	return executor.Preview{Desired: append([]domain.ComponentID(nil), desired...)}, nil
}

func applyRuntimeDigest(value int) string {
	if value == 1 {
		return "1111111111111111111111111111111111111111111111111111111111111111"
	}
	return "2222222222222222222222222222222222222222222222222222222222222222"
}

func canonicalTempDir(t *testing.T) string {
	t.Helper()
	path, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("canonicalize temporary directory: %v", err)
	}
	return path
}
