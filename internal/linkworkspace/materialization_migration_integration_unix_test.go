//go:build darwin || linux

package linkworkspace_test

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
)

func TestExecutorAtomicallyMigratesManagedSymlinkToWritableFile(t *testing.T) {
	source := t.TempDir()
	targetRoot := t.TempDir()
	newContent := []byte("writable version\n")
	oldSource := writeMaterializationMigrationSources(t, source, newContent)
	location := domain.Location{Root: domain.RootCodexConfig, Path: "agents/AGENT.md"}
	if err := os.Mkdir(filepath.Join(targetRoot, "agents"), 0o700); err != nil {
		t.Fatalf("mkdir target: %v", err)
	}
	target := filepath.Join(targetRoot, "agents/AGENT.md")
	if err := os.Symlink(oldSource, target); err != nil {
		t.Fatalf("create old link: %v", err)
	}
	workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: targetRoot})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	link, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	sum := fmt.Sprintf("%x", sha256.Sum256(newContent))
	artifact := domain.Artifact{
		Location: location, UnitID: "codex.agent",
		Ownership: domain.OwnershipManagedPrevious, RawTarget: oldSource,
		Materialization: domain.MaterializationWritableFile,
		LinkDevice:      link.Entry.Device, LinkInode: link.Entry.Inode,
		LinkBirthSeconds: link.Entry.BirthSeconds, LinkBirthNanoseconds: link.Entry.BirthNanoseconds,
	}
	preview := writablePreview("release-one", domain.OperationReplace, location, artifact)
	preview.Plan.Operations[0].SourceSHA256 = sum
	store := &memoryStore{}
	store.ownership, err = linkownership.New([]linkownership.Claim{{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		RawTarget: oldSource, ReleaseID: "old-release", IndexSHA256: testDigest,
	}})
	if err != nil {
		t.Fatalf("new ownership registry: %v", err)
	}
	runner := executor.NewWithConfiguration(
		memoryLocker{}, store, staticRefresher{preview}, workspace, workspace,
	)
	if _, err := runner.Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	assertWritableFile(t, target, string(newContent))
	if store.journal == nil || len(store.journal.Steps) != 1 ||
		!store.journal.Steps[0].Before.Exists || !store.journal.Steps[0].FileAfter.Exists ||
		store.journal.Steps[0].Phase != executor.StepPublished {
		t.Fatalf("migration journal = %#v", store.journal)
	}
	claim, exists := store.ownership.ClaimAt(location)
	if !exists || claim.Materialization != domain.MaterializationWritableFile ||
		claim.ContentSHA256 != sum || claim.Mode != 0o600 {
		t.Fatalf("migrated claim = %#v, exists = %t", claim, exists)
	}
}

func TestExecutorRecoversInterruptedMaterializationMigration(t *testing.T) {
	source := t.TempDir()
	targetRoot := t.TempDir()
	newContent := []byte("writable version\n")
	oldSource := writeMaterializationMigrationSources(t, source, newContent)
	location := domain.Location{Root: domain.RootCodexConfig, Path: "AGENT.md"}
	target := filepath.Join(targetRoot, "AGENT.md")
	if err := os.Symlink(oldSource, target); err != nil {
		t.Fatalf("create old link: %v", err)
	}
	workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: targetRoot})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	link, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	artifact := domain.Artifact{
		Location: location, UnitID: "codex.agent",
		Ownership: domain.OwnershipManagedPrevious, RawTarget: oldSource,
		Materialization: domain.MaterializationWritableFile,
		LinkDevice:      link.Entry.Device, LinkInode: link.Entry.Inode,
		LinkBirthSeconds: link.Entry.BirthSeconds, LinkBirthNanoseconds: link.Entry.BirthNanoseconds,
	}
	preview := writablePreview("release-one", domain.OperationReplace, location, artifact)
	preview.Plan.Operations[0].SourceSHA256 = fmt.Sprintf("%x", sha256.Sum256(newContent))
	store := &migrationInterruptStore{interrupt: true}
	store.ownership, err = linkownership.New([]linkownership.Claim{{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		RawTarget: oldSource, ReleaseID: "old-release", IndexSHA256: testDigest,
	}})
	if err != nil {
		t.Fatalf("new ownership registry: %v", err)
	}
	runner := executor.NewWithConfiguration(
		memoryLocker{}, store, staticRefresher{preview}, workspace, workspace,
	)
	if _, err := runner.Apply(preview); err == nil {
		t.Fatal("interrupted migration unexpectedly completed")
	}
	store.interrupt = false
	if result, err := runner.Recover(); err != nil || !result.Recovered {
		t.Fatalf("Recover() result = %#v, error = %v", result, err)
	}
	if got, err := os.Readlink(target); err != nil || got != oldSource {
		t.Fatalf("recovered target = %q, error = %v", got, err)
	}
	claim, exists := store.ownership.ClaimAt(location)
	if !exists || claim.Materialization == domain.MaterializationWritableFile || claim.RawTarget != oldSource {
		t.Fatalf("recovered claim = %#v, exists = %t", claim, exists)
	}
}

type migrationInterruptStore struct {
	memoryStore
	interrupt bool
}

func (store *migrationInterruptStore) Save(journal executor.Journal) error {
	if err := store.memoryStore.Save(journal); err != nil {
		return err
	}
	if store.interrupt && len(journal.Steps) == 1 &&
		journal.Steps[0].Phase == executor.StepPublished &&
		journal.Steps[0].ClaimPhase == executor.ClaimPrepared {
		return errors.New("injected migration interruption")
	}
	return nil
}

func writeMaterializationMigrationSources(t *testing.T, source string, current []byte) string {
	t.Helper()
	if err := os.MkdirAll(filepath.Join(source, "bundle"), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	if err := os.WriteFile(filepath.Join(source, "bundle/AGENT.md"), current, 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	oldSource := filepath.Join(source, "old-AGENT.md")
	if err := os.WriteFile(oldSource, []byte("linked version\n"), 0o644); err != nil {
		t.Fatalf("write old source: %v", err)
	}
	return oldSource
}
