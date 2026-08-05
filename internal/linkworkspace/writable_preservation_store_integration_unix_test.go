//go:build darwin || linux

package linkworkspace_test

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
)

func TestRealStoreRetainsPreservedWritableClaimWhileApplyingNeighborUpdate(t *testing.T) {
	fixture := newWritablePreservationFixture(t)
	defer fixture.state.Close()
	runner := executor.NewWithConfiguration(
		fixture.state, fixture.state, staticRefresher{fixture.preview},
		fixture.workspace, fixture.workspace,
	)
	if _, err := runner.Apply(fixture.preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	assertWritableFile(t, filepath.Join(fixture.targetRoot, "agents", "drifted.md"), "local edit\n")
	assertWritableFile(t, filepath.Join(fixture.targetRoot, "agents", "previous.md"), "version two\n")
	loaded, err := fixture.state.LoadOwnership()
	if err != nil {
		t.Fatalf("LoadOwnership() error = %v", err)
	}
	driftedClaim, exists := loaded.ClaimAt(fixture.driftedLocation)
	if !exists || driftedClaim.UnitID != "codex.drifted" || driftedClaim.ContentSHA256 != fixture.oldDigest {
		t.Fatalf("preserved claim = %#v, exists = %t", driftedClaim, exists)
	}
}

type writablePreservationFixture struct {
	workspace       linkworkspace.Workspace
	state           *executor.UnixState
	preview         executor.Preview
	targetRoot      string
	driftedLocation domain.Location
	oldDigest       string
}

func newWritablePreservationFixture(t *testing.T) writablePreservationFixture {
	t.Helper()
	source := t.TempDir()
	targetRoot := t.TempDir()
	if err := os.MkdirAll(filepath.Join(source, "bundle"), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	newContent := []byte("version two\n")
	mustWritePreservationFile(t, filepath.Join(source, "bundle", "updated.md"), newContent, 0o644)
	driftedLocation := domain.Location{Root: domain.RootCodexConfig, Path: "agents/drifted.md"}
	previousLocation := domain.Location{Root: domain.RootCodexConfig, Path: "agents/previous.md"}
	if err := os.MkdirAll(filepath.Join(targetRoot, "agents"), 0o700); err != nil {
		t.Fatalf("mkdir target: %v", err)
	}
	oldContent := []byte("version one\n")
	mustWritePreservationFile(t, filepath.Join(targetRoot, "agents", "drifted.md"), []byte("local edit\n"), 0o600)
	mustWritePreservationFile(t, filepath.Join(targetRoot, "agents", "previous.md"), oldContent, 0o600)
	workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: targetRoot})
	if err != nil {
		t.Fatalf("linkworkspace.New() error = %v", err)
	}
	previousState, err := workspace.InspectConfiguration(previousLocation)
	if err != nil {
		t.Fatalf("InspectConfiguration() error = %v", err)
	}
	previousArtifact := writableArtifact(previousLocation, previousState, domain.OwnershipManagedPrevious)
	previousArtifact.UnitID = "codex.previous"
	newDigest := fmt.Sprintf("%x", sha256.Sum256(newContent))
	preview := executor.Preview{
		Release: executor.ReleaseIdentity{ID: "release-two", IndexSHA256: testDigest},
		Desired: []domain.ComponentID{"codex"},
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: "codex", UnitID: "codex.previous", Kind: domain.OperationReplace,
			Artifact: previousArtifact, SourcePath: "bundle/updated.md", SourceSHA256: newDigest,
		}}},
	}
	oldDigest := fmt.Sprintf("%x", sha256.Sum256(oldContent))
	state := openWritablePreservationState(t, driftedLocation, previousLocation, oldDigest)
	return writablePreservationFixture{
		workspace: workspace, state: state, preview: preview, targetRoot: targetRoot,
		driftedLocation: driftedLocation, oldDigest: oldDigest,
	}
}

func openWritablePreservationState(
	t *testing.T,
	driftedLocation domain.Location,
	previousLocation domain.Location,
	oldDigest string,
) *executor.UnixState {
	t.Helper()
	registry, err := linkownership.New([]linkownership.Claim{
		{UnitID: "codex.drifted", ComponentID: "codex", Target: driftedLocation, Materialization: domain.MaterializationWritableFile, ContentSHA256: oldDigest, Mode: 0o600, ReleaseID: "release-one", IndexSHA256: testDigest},
		{UnitID: "codex.previous", ComponentID: "codex", Target: previousLocation, Materialization: domain.MaterializationWritableFile, ContentSHA256: oldDigest, Mode: 0o600, ReleaseID: "release-one", IndexSHA256: testDigest},
	})
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}
	stateBase, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("EvalSymlinks() error = %v", err)
	}
	state, err := executor.OpenUnixState(filepath.Join(stateBase, "state"))
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	if err := state.SaveOwnership(registry); err != nil {
		state.Close()
		t.Fatalf("SaveOwnership() error = %v", err)
	}
	return state
}

func mustWritePreservationFile(t *testing.T, path string, content []byte, mode os.FileMode) {
	t.Helper()
	if err := os.WriteFile(path, content, mode); err != nil {
		t.Fatalf("write %q: %v", path, err)
	}
}
