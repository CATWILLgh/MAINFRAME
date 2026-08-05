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

const testDigest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func TestExecutorRecoversJournalProducedWithUnixWorkspace(t *testing.T) {
	source := t.TempDir()
	target := filepath.Join(t.TempDir(), ".local", "bin")
	if err := os.Mkdir(filepath.Join(source, "bin"), 0o755); err != nil {
		t.Fatalf("mkdir source bin: %v", err)
	}
	if err := os.WriteFile(filepath.Join(source, "bin", "mainframe"), nil, 0o755); err != nil {
		t.Fatalf("write source: %v", err)
	}
	workspace, err := linkworkspace.New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	preview := executor.Preview{
		Release: executor.ReleaseIdentity{ID: "release", IndexSHA256: testDigest},
		Desired: []domain.ComponentID{"mainframe-cli"},
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: "mainframe-cli",
			Kind:        domain.OperationInstall,
			Artifact: domain.Artifact{Location: domain.Location{
				Root: domain.RootUserBin,
				Path: "mainframe",
			}},
			SourcePath: "bin/mainframe",
		}}},
	}
	store := &memoryStore{}
	runner := executor.New(memoryLocker{}, store, staticRefresher{preview}, workspace)
	if _, err := runner.Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if link, err := os.Lstat(filepath.Join(target, "mainframe")); err != nil ||
		link.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("managed-root install did not publish link: info=%v error=%v", link, err)
	}
	if _, err := runner.Recover(); err != nil {
		t.Fatalf("Recover() rejected its own journal: %v", err)
	}
}

func TestWritableFileLifecycleUpdatesUnchangedAndPreservesLocalEdits(t *testing.T) {
	source := t.TempDir()
	target := t.TempDir()
	if err := os.MkdirAll(filepath.Join(source, "bundle"), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	sourcePath := filepath.Join(source, "bundle", "AGENT.md")
	if err := os.WriteFile(sourcePath, []byte("version one\n"), 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: target})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	store := &memoryStore{}
	location := domain.Location{Root: domain.RootCodexConfig, Path: "agents/AGENT.md"}
	if err := os.Mkdir(filepath.Join(target, "agents"), 0o700); err != nil {
		t.Fatalf("mkdir target: %v", err)
	}

	install := writablePreview("release-one", domain.OperationInstall, location, domain.Artifact{Location: location, Materialization: domain.MaterializationWritableFile})
	applyWritablePreview(t, store, workspace, install)
	assertWritableFile(t, filepath.Join(target, "agents", "AGENT.md"), "version one\n")

	state, err := workspace.InspectConfiguration(location)
	if err != nil {
		t.Fatalf("inspect installed file: %v", err)
	}
	if err := os.WriteFile(sourcePath, []byte("version two\n"), 0o644); err != nil {
		t.Fatalf("update source: %v", err)
	}
	previous := writableArtifact(location, state, domain.OwnershipManagedPrevious)
	update := writablePreview("release-two", domain.OperationReplace, location, previous)
	applyWritablePreview(t, store, workspace, update)
	assertWritableFile(t, filepath.Join(target, "agents", "AGENT.md"), "version two\n")
	state, err = workspace.InspectConfiguration(location)
	if err != nil {
		t.Fatalf("inspect updated file: %v", err)
	}
	remove := writablePreview(
		"release-two", domain.OperationRemove, location,
		writableArtifact(location, state, domain.OwnershipManagedExact),
	)
	applyWritablePreview(t, store, workspace, remove)
	if _, err := os.Lstat(filepath.Join(target, "agents", "AGENT.md")); !os.IsNotExist(err) {
		t.Fatalf("unchanged writable file was not removed: %v", err)
	}
	install = writablePreview("release-two", domain.OperationInstall, location, domain.Artifact{Location: location, Materialization: domain.MaterializationWritableFile})
	applyWritablePreview(t, store, workspace, install)

	if err := os.WriteFile(filepath.Join(target, "agents", "AGENT.md"), []byte("local edit\n"), 0o600); err != nil {
		t.Fatalf("write local edit: %v", err)
	}
	state, err = workspace.InspectConfiguration(location)
	if err != nil {
		t.Fatalf("inspect local edit: %v", err)
	}
	drifted := writableArtifact(location, state, domain.OwnershipManagedDrifted)
	relinquish := writablePreview("release-two", domain.OperationRelinquish, location, drifted)
	applyWritablePreview(t, store, workspace, relinquish)
	assertWritableFile(t, filepath.Join(target, "agents", "AGENT.md"), "local edit\n")
	if _, exists := store.ownership.ClaimAt(location); exists {
		t.Fatal("locally edited file retained an ownership claim")
	}
}

func TestWritableFileRejectsSourceChangedAfterPreview(t *testing.T) {
	source := t.TempDir()
	target := t.TempDir()
	if err := os.MkdirAll(filepath.Join(source, "bundle"), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	sourcePath := filepath.Join(source, "bundle", "AGENT.md")
	if err := os.WriteFile(sourcePath, []byte("version one\n"), 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: target})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	location := domain.Location{Root: domain.RootCodexConfig, Path: "AGENT.md"}
	preview := writablePreview("release-one", domain.OperationInstall, location, domain.Artifact{
		Location: location, Materialization: domain.MaterializationWritableFile,
	})
	if err := os.WriteFile(sourcePath, []byte("changed after preview\n"), 0o644); err != nil {
		t.Fatalf("change source: %v", err)
	}
	store := &memoryStore{}
	runner := executor.NewWithConfiguration(memoryLocker{}, store, staticRefresher{preview}, workspace, workspace)
	if _, err := runner.Apply(preview); err == nil {
		t.Fatal("changed writable-file source was installed")
	}
	if _, err := os.Lstat(filepath.Join(target, "AGENT.md")); !os.IsNotExist(err) {
		t.Fatalf("changed source created target: %v", err)
	}
}

func TestWritableFileRecoveryCleansEmptyAndUnrecordedStages(t *testing.T) {
	for _, staged := range []bool{false, true} {
		t.Run(fmt.Sprintf("staged=%t", staged), func(t *testing.T) {
			source := t.TempDir()
			target := t.TempDir()
			if err := os.WriteFile(filepath.Join(source, "AGENT.md"), []byte("content\n"), 0o644); err != nil {
				t.Fatalf("write source: %v", err)
			}
			workspace, err := linkworkspace.New(source, map[domain.RootID]string{domain.RootCodexConfig: target})
			if err != nil {
				t.Fatalf("New() error = %v", err)
			}
			location := domain.Location{Root: domain.RootCodexConfig, Path: "AGENT.md"}
			journal := preparedWritableJournal(t, workspace, location, staged)
			store := &memoryStore{journal: &journal}
			runner := executor.NewWithConfiguration(memoryLocker{}, store, staticRefresher{}, workspace, workspace)
			result, err := runner.Recover()
			if err != nil || !result.Recovered {
				t.Fatalf("Recover() result=%#v error=%v", result, err)
			}
			if _, err := os.Lstat(filepath.Join(target, "AGENT.md")); !os.IsNotExist(err) {
				t.Fatalf("recovery published target: %v", err)
			}
			matches, err := filepath.Glob(filepath.Join(target, ".mainframe-*"))
			if err != nil || len(matches) != 0 {
				t.Fatalf("recovery left private workspace: %v, error=%v", matches, err)
			}
		})
	}
}

func preparedWritableJournal(
	t *testing.T,
	workspace linkworkspace.Workspace,
	location domain.Location,
	staged bool,
) executor.Journal {
	t.Helper()
	payload := []byte("content\n")
	sum := fmt.Sprintf("%x", sha256.Sum256(payload))
	plan := domain.Plan{Operations: []domain.Operation{{
		ComponentID: "codex", UnitID: "codex.agent", Kind: domain.OperationInstall,
		Artifact:   domain.Artifact{Location: location, Materialization: domain.MaterializationWritableFile},
		SourcePath: "AGENT.md", SourceSHA256: sum,
	}}}
	directories, err := workspace.PlanDirectories(plan)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	state, err := workspace.InspectConfiguration(location)
	if err != nil {
		t.Fatalf("InspectConfiguration() error = %v", err)
	}
	fileAfter := executor.ConfigurationFileImage{Exists: true, SHA256: sum, Mode: 0o600}
	mutation := executor.JournalConfigurationMutation{
		Disposition: executor.ConfigurationPresent, Target: location,
		After: fileAfter, Parent: state.Parent,
		Private:    executor.PrivateDirectory{Name: ".mainframe-00000000000000000000000000000001"},
		StagedName: "staged", Phase: executor.StepPrepared,
	}
	privateIdentity, err := workspace.PrepareConfigurationPrivate(mutation)
	if err != nil {
		t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
	}
	mutation.Private.Identity = privateIdentity
	if staged {
		if _, err := workspace.StageConfiguration(mutation, payload); err != nil {
			t.Fatalf("StageConfiguration() error = %v", err)
		}
	}
	claim := linkownership.Claim{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   sum, Mode: 0o600,
		ReleaseID: "release", IndexSHA256: testDigest,
	}
	return executor.Journal{
		SchemaVersion: executor.CurrentJournalSchemaVersion,
		Release:       executor.ReleaseIdentity{ID: "release", IndexSHA256: testDigest},
		Desired:       []domain.ComponentID{"codex"}, Status: executor.TransactionInProgress,
		Plan: plan, Roots: directories.Roots,
		Steps: []executor.JournalMutation{{
			ComponentID: "codex", UnitID: "codex.agent", Kind: executor.MutationInstall,
			Location: location, SourcePath: "AGENT.md", SourceSHA256: sum,
			Materialization: domain.MaterializationWritableFile,
			FileAfter:       fileAfter, Parent: state.Parent, Private: mutation.Private,
			StagedName: "staged", Phase: executor.StepPrepared,
			ClaimAfter: &claim, ClaimPhase: executor.ClaimPrepared,
		}},
	}
}

func writablePreview(release string, kind domain.OperationKind, location domain.Location, artifact domain.Artifact) executor.Preview {
	operation := domain.Operation{
		ComponentID: "codex", UnitID: "codex.agent", Kind: kind,
		Artifact: artifact,
	}
	if kind == domain.OperationInstall || kind == domain.OperationReplace {
		operation.SourcePath = "bundle/AGENT.md"
		sum := sha256.Sum256([]byte(map[string]string{
			"release-one": "version one\n",
			"release-two": "version two\n",
		}[release]))
		operation.SourceSHA256 = fmt.Sprintf("%x", sum)
	}
	return executor.Preview{
		Release: executor.ReleaseIdentity{ID: release, IndexSHA256: testDigest},
		Desired: []domain.ComponentID{"codex"},
		Plan:    domain.Plan{Operations: []domain.Operation{operation}},
	}
}

func applyWritablePreview(t *testing.T, store *memoryStore, workspace linkworkspace.Workspace, preview executor.Preview) {
	t.Helper()
	store.journal = nil
	runner := executor.NewWithConfiguration(memoryLocker{}, store, staticRefresher{preview}, workspace, workspace)
	if _, err := runner.Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
}

func writableArtifact(location domain.Location, state executor.ConfigurationState, status domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{
		Location: location, UnitID: "codex.agent", Ownership: status,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   state.SHA256, Mode: state.Mode,
		LinkDevice: state.Entry.Device, LinkInode: state.Entry.Inode,
		LinkBirthSeconds:     state.Entry.BirthSeconds,
		LinkBirthNanoseconds: state.Entry.BirthNanoseconds,
	}
}

func assertWritableFile(t *testing.T, path string, want string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read writable file: %v", err)
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 || string(content) != want {
		t.Fatalf("writable file content=%q mode=%v error=%v", content, info.Mode(), err)
	}
}

type memoryStore struct {
	journal   *executor.Journal
	ownership linkownership.Registry
}

func (store *memoryStore) LoadOwnership() (linkownership.Registry, error) {
	return linkownership.New(store.ownership.Claims())
}

func (store *memoryStore) SaveOwnership(registry linkownership.Registry) error {
	stored, err := linkownership.New(registry.Claims())
	if err == nil {
		store.ownership = stored
	}
	return err
}

func (store *memoryStore) Load() (*executor.Journal, error) {
	return store.journal, nil
}

func (store *memoryStore) Save(journal executor.Journal) error {
	clone := journal
	clone.Desired = append([]domain.ComponentID(nil), journal.Desired...)
	clone.Plan.Operations = append(
		[]domain.Operation(nil),
		journal.Plan.Operations...,
	)
	clone.Roots = append([]executor.RootSnapshot(nil), journal.Roots...)
	clone.Directories = append(
		[]executor.JournalDirectory(nil),
		journal.Directories...,
	)
	clone.Steps = append([]executor.JournalMutation(nil), journal.Steps...)
	store.journal = &clone
	return nil
}

func (store *memoryStore) Cleanup() error {
	return nil
}

type memoryLocker struct{}

func (memoryLocker) Lock() (executor.Lock, error) {
	return memoryLock{}, nil
}

type memoryLock struct{}

func (memoryLock) Unlock() error {
	return nil
}

type staticRefresher struct {
	preview executor.Preview
}

func (refresher staticRefresher) Refresh([]domain.ComponentID) (executor.Preview, error) {
	return refresher.preview, nil
}
