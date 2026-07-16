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
	if len(fixture.store.saves) != 4 {
		t.Fatalf("journal saves = %d, want prepared, confirmed, applied, committed", len(fixture.store.saves))
	}
	prepared := fixture.store.saves[0].Steps[0]
	if prepared.State != StepPrepared || prepared.Location != testLocation("one") ||
		prepared.SourcePath != "source/one" || prepared.Before.Exists ||
		prepared.After != (LinkImage{Exists: true, RawTarget: "source/one"}) ||
		prepared.Parent != (FileIdentity{Device: 1, Inode: 1}) {
		t.Fatalf("prepared journal mutation = %#v", prepared)
	}
	confirmed := fixture.store.saves[1].Steps[0]
	if confirmed.State != StepPrepared || confirmed.After.Entry == (FileIdentity{}) ||
		fixture.store.saves[2].Steps[0].State != StepApplied ||
		fixture.store.saves[3].Status != TransactionCommitted {
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
	for _, failedSave := range []int{1, 3, 4, 6, 7} {
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

func TestApplyFailsClosedWhenPublishedIdentityCannotBeJournaled(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("one", "source/one"),
		install("two", "source/two"),
	)
	for _, failedSave := range []int{2, 5} {
		t.Run(fmt.Sprintf("save-%d", failedSave), func(t *testing.T) {
			fixture := newFixture(preview)
			fixture.store.saveFailAt = failedSave

			_, err := fixture.executor().Apply(preview)

			if err == nil || !strings.Contains(err.Error(), "save confirmed mutation") {
				t.Fatalf("expected confirmed identity save failure, got %v", err)
			}
			if !fixture.workspace.links[testLocation("one")].Exists {
				t.Fatal("unconfirmed installed link was unsafely rolled back")
			}
			last := fixture.store.journal.Steps[len(fixture.store.journal.Steps)-1]
			if last.After.Entry != (FileIdentity{}) || fixture.store.cleanupCalls != 0 {
				t.Fatalf("unsafe confirmation failure state: journal=%#v cleanup=%d", fixture.store.journal, fixture.store.cleanupCalls)
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
	fixture.workspace.replaceFailAt = 2
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
	fixture.workspace.replaceFailAt = 2

	_, err := fixture.executor().Apply(preview)

	if err == nil {
		t.Fatal("expected replacement failure")
	}
	got := fixture.workspace.links[location]
	if !got.Exists || got.RawTarget != "source/old" ||
		got.Parent != (FileIdentity{Device: 1, Inode: 1}) {
		t.Fatalf("removed link restored as %#v", got)
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
		Parent: FileIdentity{Device: 1, Inode: 1},
		Entry:  FileIdentity{Device: 1, Inode: 2},
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
