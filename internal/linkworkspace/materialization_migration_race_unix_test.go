//go:build darwin || linux

package linkworkspace

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestRestoreChangedMigrationPublicationPreservesForeignEntry(t *testing.T) {
	source := t.TempDir()
	targetRoot := t.TempDir()
	location := domain.Location{Root: domain.RootCodexConfig, Path: "AGENT.md"}
	oldTarget := filepath.Join(source, "old.md")
	foreignTarget := filepath.Join(source, "foreign.md")
	for path, content := range map[string][]byte{
		oldTarget: []byte("old\n"), foreignTarget: []byte("foreign\n"),
	} {
		if err := os.WriteFile(path, content, 0o644); err != nil {
			t.Fatalf("write source: %v", err)
		}
	}
	if err := os.Symlink(oldTarget, filepath.Join(targetRoot, "AGENT.md")); err != nil {
		t.Fatalf("create old link: %v", err)
	}
	workspace, err := New(source, map[domain.RootID]string{domain.RootCodexConfig: targetRoot})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	step := stagedMigrationStep(t, workspace, location, oldTarget)
	context, err := workspace.openConfigurationMutation(migrationConfiguration(step))
	if err != nil {
		t.Fatalf("open mutation: %v", err)
	}
	defer context.close()
	if err := renameExchange(context.privateFD, step.StagedName, context.parentFD, context.finalName); err != nil {
		t.Fatalf("simulate exchange: %v", err)
	}
	retained := filepath.Join(targetRoot, step.Private.Name, step.StagedName)
	if err := os.Remove(retained); err != nil {
		t.Fatalf("remove retained link: %v", err)
	}
	if err := os.Symlink(foreignTarget, retained); err != nil {
		t.Fatalf("replace retained link: %v", err)
	}
	err = restoreChangedMigrationPublication(context, step)
	if err != nil {
		t.Fatalf("restore error = %v", err)
	}
	if got, readErr := os.Readlink(filepath.Join(targetRoot, "AGENT.md")); readErr != nil || got != foreignTarget {
		t.Fatalf("public target = %q, error = %v", got, readErr)
	}
}

func TestRecoveryRestoresForeignEntryDisplacedByMigrationExchange(t *testing.T) {
	source := t.TempDir()
	targetRoot := t.TempDir()
	location := domain.Location{Root: domain.RootCodexConfig, Path: "AGENT.md"}
	oldTarget := filepath.Join(source, "old.md")
	foreignTarget := filepath.Join(source, "foreign.md")
	for path, content := range map[string][]byte{
		oldTarget: []byte("old\n"), foreignTarget: []byte("foreign\n"),
	} {
		if err := os.WriteFile(path, content, 0o644); err != nil {
			t.Fatalf("write source: %v", err)
		}
	}
	public := filepath.Join(targetRoot, "AGENT.md")
	if err := os.Symlink(oldTarget, public); err != nil {
		t.Fatalf("create old link: %v", err)
	}
	workspace, err := New(source, map[domain.RootID]string{domain.RootCodexConfig: targetRoot})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	step := stagedMigrationStep(t, workspace, location, oldTarget)
	private := filepath.Join(targetRoot, step.Private.Name, step.StagedName)
	arrangeInterruptedMigrationEntry(t, public, private, foreignTarget, targetRoot)
	operation := migrationOperation(step, location)
	directories, err := workspace.PlanDirectories(domain.Plan{Operations: []domain.Operation{operation}})
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	beforeClaim, afterClaim := migrationClaims(step, location, oldTarget)
	step.ClaimBefore, step.ClaimAfter = &beforeClaim, &afterClaim
	step.ClaimPhase = executor.ClaimPrepared
	store := &migrationRecoveryStore{journal: &executor.Journal{
		SchemaVersion: executor.CurrentJournalSchemaVersion,
		Release:       executor.ReleaseIdentity{ID: "release", IndexSHA256: migrationTestDigest},
		Desired:       []domain.ComponentID{"codex"}, Status: executor.TransactionInProgress,
		Plan: domain.Plan{Operations: []domain.Operation{operation}}, Roots: directories.Roots,
		Steps: []executor.JournalMutation{step},
	}}
	store.ownership, err = linkownership.New([]linkownership.Claim{beforeClaim})
	if err != nil {
		t.Fatalf("new ownership: %v", err)
	}
	runner := executor.NewWithConfiguration(migrationRecoveryLocker{}, store, nil, workspace, workspace)
	if result, err := runner.Recover(); err != nil || !result.Recovered {
		t.Fatalf("Recover() result = %#v, error = %v", result, err)
	}
	if got, err := os.Readlink(public); err != nil || got != foreignTarget {
		t.Fatalf("public target = %q, error = %v", got, err)
	}
}

func arrangeInterruptedMigrationEntry(
	t *testing.T,
	public, private, foreignTarget, targetRoot string,
) {
	t.Helper()
	displaced := filepath.Join(targetRoot, "displaced")
	if err := os.Remove(public); err != nil {
		t.Fatalf("remove old link: %v", err)
	}
	if err := os.Symlink(foreignTarget, public); err != nil {
		t.Fatalf("create foreign link: %v", err)
	}
	for _, move := range [][2]string{{public, displaced}, {private, public}, {displaced, private}} {
		if err := os.Rename(move[0], move[1]); err != nil {
			t.Fatalf("arrange interrupted exchange: %v", err)
		}
	}
}

const migrationTestDigest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func migrationOperation(step executor.JournalMutation, location domain.Location) domain.Operation {
	return domain.Operation{
		ComponentID: "codex", UnitID: "codex.agent", Kind: domain.OperationReplace,
		Artifact: domain.Artifact{
			Location: location, UnitID: "codex.agent",
			Ownership: domain.OwnershipManagedPrevious, RawTarget: step.Before.RawTarget,
			Materialization: domain.MaterializationWritableFile,
			LinkDevice:      step.Before.Entry.Device, LinkInode: step.Before.Entry.Inode,
			LinkBirthSeconds:     step.Before.Entry.BirthSeconds,
			LinkBirthNanoseconds: step.Before.Entry.BirthNanoseconds,
		},
		SourcePath: step.SourcePath, SourceSHA256: step.SourceSHA256,
	}
}

func migrationClaims(
	step executor.JournalMutation,
	location domain.Location,
	oldTarget string,
) (linkownership.Claim, linkownership.Claim) {
	before := linkownership.Claim{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		RawTarget: oldTarget, ReleaseID: "old-release", IndexSHA256: migrationTestDigest,
	}
	after := linkownership.Claim{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   step.FileAfter.SHA256, Mode: step.FileAfter.Mode,
		ReleaseID: "release", IndexSHA256: migrationTestDigest,
	}
	return before, after
}

type migrationRecoveryStore struct {
	journal   *executor.Journal
	ownership linkownership.Registry
}

func (store *migrationRecoveryStore) Load() (*executor.Journal, error) { return store.journal, nil }
func (store *migrationRecoveryStore) Save(journal executor.Journal) error {
	store.journal = &journal
	return nil
}
func (store *migrationRecoveryStore) Cleanup() error { store.journal = nil; return nil }
func (store *migrationRecoveryStore) LoadOwnership() (linkownership.Registry, error) {
	return linkownership.New(store.ownership.Claims())
}
func (store *migrationRecoveryStore) SaveOwnership(registry linkownership.Registry) error {
	store.ownership = registry
	return nil
}

type migrationRecoveryLocker struct{}
type migrationRecoveryLock struct{}

func (migrationRecoveryLocker) Lock() (executor.Lock, error) { return migrationRecoveryLock{}, nil }
func (migrationRecoveryLock) Unlock() error                  { return nil }

func stagedMigrationStep(
	t *testing.T,
	workspace Workspace,
	location domain.Location,
	oldTarget string,
) executor.JournalMutation {
	t.Helper()
	link, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("inspect link: %v", err)
	}
	payload := []byte("managed\n")
	digest := fmt.Sprintf("%x", sha256.Sum256(payload))
	step := executor.JournalMutation{
		ComponentID: "codex", UnitID: "codex.agent",
		Kind: executor.MutationReplace, Location: location,
		SourcePath: "AGENT.md", SourceSHA256: digest,
		Materialization: domain.MaterializationWritableFile,
		Before:          executor.LinkImage{Exists: true, RawTarget: oldTarget, Entry: link.Entry},
		FileAfter:       executor.ConfigurationFileImage{Exists: true, SHA256: digest, Mode: 0o600},
		Parent:          link.Parent, Private: executor.PrivateDirectory{Name: ".mainframe-00000000000000000000000000000001"},
		StagedName: "staged", RetainedName: "staged", Phase: executor.StepPrepared,
	}
	mutation := migrationConfiguration(step)
	step.Private.Identity, err = workspace.PrepareConfigurationPrivate(mutation)
	if err != nil {
		t.Fatalf("prepare private: %v", err)
	}
	mutation = migrationConfiguration(step)
	step.StagedIdentity, err = workspace.StageConfiguration(mutation, payload)
	if err != nil {
		t.Fatalf("stage configuration: %v", err)
	}
	step.Phase = executor.StepStaged
	return step
}
