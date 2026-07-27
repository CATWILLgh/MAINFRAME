package executor

import (
	"errors"
	"fmt"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

var errCleanup = errors.New("cleanup failed")

func TestApplyPersistsPreparedMutationBeforeAtomicReplacement(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err != nil {
		t.Fatalf("apply: %v", err)
	}
	if len(fixture.store.saves) != 6 {
		t.Fatalf("journal saves = %d, want all protocol boundaries", len(fixture.store.saves))
	}
	prepared := fixture.store.saves[0].Steps[0]
	if prepared.Phase != StepPrepared || prepared.Location != testLocation("one") ||
		prepared.SourcePath != "source/one" || prepared.Before.Exists ||
		prepared.After != (LinkImage{Exists: true, RawTarget: "source/one"}) ||
		prepared.Parent != testIdentity(1, 1) {
		t.Fatalf("prepared journal mutation = %#v", prepared)
	}
	staged := fixture.store.saves[2].Steps[0]
	if staged.Phase != StepStaged || staged.StagedIdentity == (FileIdentity{}) ||
		fixture.store.saves[3].Steps[0].Phase != StepPublished ||
		fixture.store.saves[4].Status != TransactionCommitted ||
		!fixture.store.saves[5].Steps[0].Finalized {
		t.Fatalf("journal state sequence = %#v", fixture.store.saves)
	}
	if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
		t.Fatalf("successful transaction did not clean journal")
	}
}

func TestApplyRollsBackAfterEveryJournalBoundaryFailure(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	for _, failedSave := range []int{1, 2, 3, 4, 5, 6, 7, 8} {
		t.Run(string(rune('0'+failedSave)), func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.store.saveFailAt = failedSave

			_, err := fixture.executor().Apply(preview)

			if err == nil || !strings.Contains(err.Error(), "save") {
				t.Fatalf("expected save failure, got %v", err)
			}
			assertAbsent(t, fixture.workspace, "one", "two")
			if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
				t.Fatalf("failure %d left journal %#v", failedSave, fixture.store.journal)
			}
		})
	}
}

func TestApplyDefersCommitSaveFailureToRecoveryWithoutRollback(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	tests := []struct {
		name                  string
		failAfterWrite        bool
		wantJournalStatus     TransactionStatus
		wantLinksAfterRecover bool
	}{
		{name: "commit not persisted", wantJournalStatus: TransactionInProgress},
		{name: "commit persisted despite error", failAfterWrite: true,
			wantJournalStatus: TransactionCommitted, wantLinksAfterRecover: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(preview)
			if test.failAfterWrite {
				fixture.store.saveFailAfterWriteAt = 9
			} else {
				fixture.store.saveFailAt = 9
			}

			_, applyErr := fixture.executor().Apply(preview)

			if applyErr == nil || fixture.store.cleanupCalls != 0 {
				t.Fatalf("commit failure was not deferred: error=%v cleanup=%d", applyErr, fixture.store.cleanupCalls)
			}
			if fixture.store.journal == nil || fixture.store.journal.Status != test.wantJournalStatus {
				t.Fatalf("journal after commit failure = %#v", fixture.store.journal)
			}
			if !fixture.workspace.links[testLocation("one")].Exists ||
				!fixture.workspace.links[testLocation("two")].Exists {
				t.Fatal("current process rolled back after attempting commit")
			}
			fixture.store.saveFailAt = 0
			fixture.store.saveFailAfterWriteAt = 0
			if _, err := fixture.executor().Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}
			for _, path := range []domain.ArtifactPath{"one", "two"} {
				if fixture.workspace.links[testLocation(path)].Exists != test.wantLinksAfterRecover {
					t.Fatalf("recovered link %q existence differs", path)
				}
			}
		})
	}
}

func TestApplyRetainsCommittedJournalWhenFinalizationSaveFails(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	for _, failedSave := range []int{10, 11} {
		t.Run(fmt.Sprintf("save-%d", failedSave), func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.store.saveFailAt = failedSave

			_, err := fixture.executor().Apply(preview)

			if err == nil || !strings.Contains(err.Error(), "finalize committed") {
				t.Fatalf("expected finalization save failure, got %v", err)
			}
			if fixture.store.journal == nil ||
				fixture.store.journal.Status != TransactionCommitted {
				t.Fatalf("committed journal lost: %#v", fixture.store.journal)
			}
			if !fixture.workspace.links[testLocation("one")].Exists ||
				!fixture.workspace.links[testLocation("two")].Exists {
				t.Fatal("committed links were rolled back")
			}
		})
	}
}

func TestApplySafelyRollsBackWhenStagedOrPublishedIdentitySaveFails(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	for _, failedSave := range []int{3, 4, 7, 8} {
		t.Run(fmt.Sprintf("save-%d", failedSave), func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.store.saveFailAt = failedSave

			_, err := fixture.executor().Apply(preview)

			if err == nil || !strings.Contains(err.Error(), "save") {
				t.Fatalf("expected identity save failure, got %v", err)
			}
			assertAbsent(t, fixture.workspace, "one", "two")
			if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
				t.Fatalf("safe rollback state: journal=%#v cleanup=%d", fixture.store.journal, fixture.store.cleanupCalls)
			}
		})
	}
}

func TestApplyRollsBackPossiblyAppliedMutationInReverseOrder(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	fixture := newFixture(preview)
	fixture.workspace.publishFailAt = 2
	fixture.workspace.failAfterWrite = true

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "outcome unknown") {
		t.Fatalf("expected uncertain replace failure, got %v", err)
	}
	want := []string{"one:source/one", "two:source/two", "two:", "one:"}
	if !reflect.DeepEqual(fixture.workspace.writes, want) {
		t.Fatalf("replacement order = %#v, want %#v", fixture.workspace.writes, want)
	}
	assertAbsent(t, fixture.workspace, "one", "two")
}

func TestApplyRestoresRemovedRawLinkOnLaterFailure(t *testing.T) {
	location := testLocation("old")
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		remove("old"),
		install("new", "source/new"),
	)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = linkState("source/old")
	fixture.workspace.publishFailAt = 2

	_, err := fixture.executor().Apply(preview)

	if err == nil {
		t.Fatal("expected replacement failure")
	}
	got := fixture.workspace.links[location]
	if !got.Exists || got.RawTarget != "source/old" ||
		got.Parent != testIdentity(1, 1) {
		t.Fatalf("removed link restored as %#v", got)
	}
}

func TestApplyRecoversAcrossWorkspaceProtocolFailures(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	tests := []struct {
		name string
		fail func(*fakeWorkspace)
	}{
		{name: "allocate", fail: func(workspace *fakeWorkspace) {
			workspace.allocateErr = errors.New("allocate failed")
		}},
		{name: "prepare", fail: func(workspace *fakeWorkspace) { workspace.prepareFailAt = 1 }},
		{name: "stage", fail: func(workspace *fakeWorkspace) { workspace.stageFailAt = 1 }},
		{name: "publish", fail: func(workspace *fakeWorkspace) { workspace.publishFailAt = 1 }},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(preview)
			test.fail(fixture.workspace)

			_, err := fixture.executor().Apply(preview)

			if err == nil {
				t.Fatal("expected protocol failure")
			}
			assertAbsent(t, fixture.workspace, "one")
			if fixture.store.journal != nil {
				t.Fatalf("protocol failure left journal: %#v", fixture.store.journal)
			}
		})
	}
}

func TestApplyLeavesCommittedJournalForRecoverableFinalizeFailure(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(preview)
	fixture.workspace.finalizeFailAt = 1

	_, applyErr := fixture.executor().Apply(preview)
	fixture.workspace.finalizeFailAt = 0
	_, recoverErr := fixture.executor().Recover()

	if applyErr == nil || !strings.Contains(applyErr.Error(), "finalize committed") {
		t.Fatalf("expected finalize failure, got %v", applyErr)
	}
	if recoverErr != nil {
		t.Fatalf("recover finalized transaction: %v", recoverErr)
	}
	if !fixture.workspace.links[testLocation("one")].Exists {
		t.Fatal("committed link was rolled back")
	}
	if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
		t.Fatalf("recovery cleanup journal=%#v calls=%d", fixture.store.journal, fixture.store.cleanupCalls)
	}
}

func TestApplyTreatsCommittedCleanupFailureAsWarning(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(preview)
	fixture.store.cleanupErr = errCleanup

	result, err := fixture.executor().Apply(preview)

	if err != nil {
		t.Fatalf("cleanup after commit must not fail apply: %v", err)
	}
	if len(result.Warnings) != 1 || !strings.Contains(result.Warnings[0], "cleanup committed journal") {
		t.Fatalf("warnings = %#v", result.Warnings)
	}
	if fixture.store.journal == nil || fixture.store.journal.Status != TransactionCommitted {
		t.Fatalf("committed journal not retained for recovery: %#v", fixture.store.journal)
	}
	if !fixture.workspace.links[testLocation("one")].Exists {
		t.Fatal("committed mutation was rolled back")
	}
}

func remove(path domain.ArtifactPath) domain.Operation {
	return domain.Operation{
		ComponentID: "codex",
		Kind:        domain.OperationRemove,
		Artifact: domain.Artifact{
			Location:  testLocation(path),
			Ownership: domain.OwnershipManagedExact,
		},
		SourcePath: domain.ArtifactPath("source/" + string(path)),
	}
}

func linkState(target string) LinkState {
	return LinkState{
		Exists: true, RawTarget: target,
		Parent: testIdentity(1, 1),
		Entry:  testIdentity(1, 2),
	}
}

func assertAbsent(t *testing.T, workspace *fakeWorkspace, paths ...domain.ArtifactPath) {
	t.Helper()
	for _, artifactPath := range paths {
		if workspace.links[testLocation(artifactPath)].Exists {
			t.Fatalf("%q still exists", artifactPath)
		}
	}
}
