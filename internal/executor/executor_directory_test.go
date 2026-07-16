package executor

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestApplyChecksDirectoryModeBeforeManagedDirectoryIntent(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("mainframe", "source/mainframe"),
	)
	fixture := newFixture(preview)
	fixture.workspace.directoryPlan = managedDirectoryPlan(".codex")
	fixture.workspace.directoryModeErr = errors.New("unsupported process umask")

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "unsupported process umask") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.directoryModeChecks != 1 {
		t.Fatalf(
			"directory mode checks = %d, want 1",
			fixture.workspace.directoryModeChecks,
		)
	}
	if fixture.store.saveCalls != 0 || fixture.workspace.filesystemCalls() != 0 {
		t.Fatalf(
			"preflight wrote state: saves=%d filesystem=%d",
			fixture.store.saveCalls,
			fixture.workspace.filesystemCalls(),
		)
	}
}

func TestRecoverChecksDirectoryModeBeforePreparedDirectoryMutation(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("mainframe", "source/mainframe"),
	)
	fixture := newFixture(preview)
	directoryPlan := managedDirectoryPlan(".codex")
	fixture.workspace.directoryPlan = directoryPlan
	fixture.workspace.directoryModeErr = errors.New("unsupported process umask")
	fixture.store.journal = &Journal{
		SchemaVersion: CurrentJournalSchemaVersion,
		Release:       preview.Release,
		Desired:       append([]domain.ComponentID(nil), preview.Desired...),
		Status:        TransactionInProgress,
		Plan:          preview.Plan,
		Roots:         append([]RootSnapshot(nil), directoryPlan.Roots...),
		Directories: []JournalDirectory{{
			Target:      directoryPlan.Missing[0].Target,
			Mode:        directoryPlan.Missing[0].Mode,
			Parent:      FileIdentity{Device: 1, Inode: 1},
			PrivateName: ".mainframe-00000000000000000000000000000001",
			Phase:       StepPrepared,
		}},
	}

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "unsupported process umask") {
		t.Fatalf("Recover() error = %v", err)
	}
	if fixture.store.saveCalls != 0 || fixture.workspace.filesystemCalls() != 0 {
		t.Fatalf(
			"recovery preflight wrote state: saves=%d filesystem=%d",
			fixture.store.saveCalls,
			fixture.workspace.filesystemCalls(),
		)
	}
}

func TestApplyPersistsAllDirectoryIntentsBeforeFilesystemMutation(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("skills/mainframe", "source/mainframe"),
	)
	fixture := newFixture(preview)
	fixture.workspace.directoryPlan = managedDirectoryPlan(".codex", ".codex/skills")

	_, err := fixture.executor().Apply(preview)

	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	first := fixture.store.saves[0]
	if len(first.Directories) != 2 {
		t.Fatalf("first journal has %d directories", len(first.Directories))
	}
	for index, directory := range first.Directories {
		if directory.Phase != StepPrepared || directory.PrivateName == "" {
			t.Fatalf("directory %d intent = %#v", index, directory)
		}
	}
	if fixture.workspace.directoryInspectSave != 1 {
		t.Fatalf(
			"directory inspection saw %d journal saves, want 1",
			fixture.workspace.directoryInspectSave,
		)
	}
	if fixture.workspace.directoryStageSave != 2 {
		t.Fatalf(
			"directory staging saw %d journal saves, want persisted parent identity",
			fixture.workspace.directoryStageSave,
		)
	}
	if fixture.workspace.directoryPublishSave != 3 {
		t.Fatalf(
			"directory publication saw %d journal saves, want persisted staged identity",
			fixture.workspace.directoryPublishSave,
		)
	}
	if fixture.workspace.linkInspectDirCalls != 6 {
		t.Fatalf(
			"link inspection started after %d directory calls, want all directories published",
			fixture.workspace.linkInspectDirCalls,
		)
	}
}

func TestApplyRollsBackLinksBeforeManagedDirectoriesInReverseOrder(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("skills/mainframe", "source/mainframe"),
	)
	fixture := newFixture(preview)
	fixture.workspace.directoryPlan = managedDirectoryPlan(".codex", ".codex/skills")
	fixture.workspace.publishFailAt = 1
	fixture.workspace.failAfterWrite = true

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "outcome unknown") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.linkRollbackDirCalls != 6 {
		t.Fatalf(
			"link rollback started after %d directory calls",
			fixture.workspace.linkRollbackDirCalls,
		)
	}
	wantSuffix := []string{
		"rollback:.codex/skills",
		"finalize:.codex/skills",
		"rollback:.codex",
		"finalize:.codex",
	}
	calls := fixture.workspace.directoryCalls
	if len(calls) < len(wantSuffix) ||
		!reflect.DeepEqual(calls[len(calls)-len(wantSuffix):], wantSuffix) {
		t.Fatalf("directory rollback order = %#v", calls)
	}
	if len(fixture.workspace.directories) != 0 {
		t.Fatalf("managed directories remain = %#v", fixture.workspace.directories)
	}
}

func TestApplyRollsBackManagedDirectoryAcrossJournalSaveFailures(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("mainframe", "source/mainframe"),
	)
	for failedSave := 1; failedSave <= 4; failedSave++ {
		t.Run(string(rune('0'+failedSave)), func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.workspace.directoryPlan = managedDirectoryPlan(".codex")
			fixture.store.saveFailAt = failedSave

			_, err := fixture.executor().Apply(preview)

			if err == nil || !strings.Contains(err.Error(), "save") {
				t.Fatalf("Apply() error = %v", err)
			}
			if len(fixture.workspace.directories) != 0 ||
				len(fixture.workspace.privateDirectories) != 0 {
				t.Fatalf(
					"directory state = public %#v private %#v",
					fixture.workspace.directories,
					fixture.workspace.privateDirectories,
				)
			}
			if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
				t.Fatalf(
					"journal = %#v cleanup calls = %d",
					fixture.store.journal,
					fixture.store.cleanupCalls,
				)
			}
		})
	}
}

func TestRecoverHonorsPersistedCommitStatusForManagedDirectory(t *testing.T) {
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"codex"},
		install("mainframe", "source/mainframe"),
	)
	tests := []struct {
		name           string
		failAfterWrite bool
		wantInstalled  bool
	}{
		{name: "in progress rolls back"},
		{name: "committed stays installed", failAfterWrite: true, wantInstalled: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.workspace.directoryPlan = managedDirectoryPlan(".codex")
			if test.failAfterWrite {
				fixture.store.saveFailAfterWriteAt = 9
			} else {
				fixture.store.saveFailAt = 9
			}

			if _, err := fixture.executor().Apply(preview); err == nil {
				t.Fatal("Apply() unexpectedly succeeded")
			}
			fixture.store.saveFailAt = 0
			fixture.store.saveFailAfterWriteAt = 0
			if _, err := fixture.executor().Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}

			_, directoryExists := fixture.workspace.directories[DirectoryTarget{Root: domain.RootCodexConfig, Path: ".codex"}]
			linkExists := fixture.workspace.links[testLocation("mainframe")].Exists
			if directoryExists != test.wantInstalled || linkExists != test.wantInstalled {
				t.Fatalf(
					"recovered state: directory=%t link=%t",
					directoryExists,
					linkExists,
				)
			}
		})
	}
}

func managedDirectoryPlan(paths ...string) *DirectoryPlan {
	root := RootSnapshot{
		Root:           domain.RootCodexConfig,
		AnchorPath:     "/home/user",
		AnchorIdentity: FileIdentity{Device: 1, Inode: 1},
		RootPath:       ".codex",
	}
	plan := &DirectoryPlan{Roots: []RootSnapshot{root}}
	for _, targetPath := range paths {
		plan.Missing = append(plan.Missing, DirectoryRequirement{
			Target: DirectoryTarget{Root: domain.RootCodexConfig, Path: targetPath},
			Mode:   ManagedDirectoryMode,
		})
	}
	return plan
}
