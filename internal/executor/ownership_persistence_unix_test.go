//go:build unix

package executor

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestUnixStatePersistsOwnershipRegistryAtomically(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state, err := OpenUnixState(root)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	defer state.Close()
	registry, err := linkownership.New([]linkownership.Claim{{
		UnitID: "codex.instructions", ComponentID: "codex",
		Target:    domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
		RawTarget: "/releases/current/AGENTS.md", ReleaseID: "current-release",
		IndexSHA256: testDigest("release"),
	}})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	if err := state.SaveOwnership(registry); err != nil {
		t.Fatalf("SaveOwnership() error = %v", err)
	}
	loaded, err := state.LoadOwnership()
	if err != nil || len(loaded.Claims()) != 1 || loaded.Claims()[0] != registry.Claims()[0] {
		t.Fatalf("LoadOwnership() = %#v, %v", loaded.Claims(), err)
	}
	info, err := os.Stat(filepath.Join(root, "link-ownership.json"))
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("ownership registry mode = %v, error = %v", info.Mode().Perm(), err)
	}
}

func TestReadUnixOwnershipDoesNotCreateMissingState(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "missing", "mainframe")

	registry, err := ReadUnixOwnership(root)
	if err != nil {
		t.Fatalf("ReadUnixOwnership() error = %v", err)
	}
	if len(registry.Claims()) != 0 {
		t.Fatalf("ReadUnixOwnership() claims = %#v", registry.Claims())
	}
	if _, err := os.Stat(root); !os.IsNotExist(err) {
		t.Fatalf("read-only ownership lookup created state: %v", err)
	}
}

func TestReadUnixOwnershipLoadsExistingRegistry(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state, err := OpenUnixState(root)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	registry, err := linkownership.New([]linkownership.Claim{{
		UnitID: "codex.instructions", ComponentID: "codex",
		Target:    domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
		RawTarget: "/releases/old/AGENTS.md", ReleaseID: "old-release",
		IndexSHA256: testDigest("old"),
	}})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	if err := state.SaveOwnership(registry); err != nil {
		t.Fatalf("SaveOwnership() error = %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}

	loaded, err := ReadUnixOwnership(root)
	if err != nil || len(loaded.Claims()) != 1 || loaded.Claims()[0] != registry.Claims()[0] {
		t.Fatalf("ReadUnixOwnership() = %#v, %v", loaded.Claims(), err)
	}
}

func TestReadUnixOwnershipRejectsUnsafeStateMetadata(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state, err := OpenUnixState(root)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}
	if err := os.Chmod(root, 0o755); err != nil {
		t.Fatalf("chmod state root: %v", err)
	}

	if _, err := ReadUnixOwnership(root); err == nil {
		t.Fatal("ReadUnixOwnership() accepted unsafe state metadata")
	}
}
