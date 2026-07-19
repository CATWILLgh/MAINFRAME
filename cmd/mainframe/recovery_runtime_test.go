package main

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestBuildRecoveryServiceIgnoresReleaseAndDataPaths(t *testing.T) {
	home := canonicalTempDir(t)
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	t.Setenv("HOME", home)
	t.Setenv("XDG_STATE_HOME", stateBase)
	t.Setenv("XDG_DATA_HOME", "invalid-relative-data")
	t.Setenv(releaseRootEnvironment, "invalid-relative-release")

	service, err := buildRecoveryService()
	if err != nil {
		t.Fatalf("buildRecoveryService() error = %v", err)
	}
	stateRoot := filepath.Join(stateBase, "mainframe")
	if _, err := os.Stat(stateRoot); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("building recovery service created state: %v", err)
	}

	if _, err := service.Recover(); err != nil {
		t.Fatalf("Recover() error = %v", err)
	}
	if metadata, err := os.Stat(stateRoot); err != nil || !metadata.IsDir() {
		t.Fatalf("state root after Recover() = %#v, %v", metadata, err)
	}
}

func TestProductionRecoveryFactoryDefersUnusedTargetPinning(t *testing.T) {
	home := canonicalTempDir(t)
	blocker := filepath.Join(home, ".config")
	if err := os.WriteFile(blocker, []byte("not a directory"), 0o600); err != nil {
		t.Fatalf("write blocker: %v", err)
	}
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	t.Setenv("HOME", home)
	t.Setenv("XDG_STATE_HOME", stateBase)

	service, err := buildRecoveryService()
	if err != nil {
		t.Fatalf("buildRecoveryService() error = %v", err)
	}
	if _, err := service.Recover(); err != nil {
		t.Fatalf("Recover() with empty journal error = %v", err)
	}
}
