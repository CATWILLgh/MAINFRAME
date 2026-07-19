package main

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

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
		releaseRoot: releaseRoot,
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
		releaseRoot: releaseRoot,
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
