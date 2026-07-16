package executor

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestRecoverTreatsPreparedMutationAsPossiblyApplied(t *testing.T) {
	step := installJournalStep("one", StepPrepared)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	fixture.workspace.links[step.Location] = stateOf(step.After, step.Parent)

	_, err := fixture.executor().Recover()

	if err != nil {
		t.Fatalf("recover: %v", err)
	}
	assertAbsent(t, fixture.workspace, "one")
	if fixture.store.journal != nil || fixture.store.cleanupCalls != 1 {
		t.Fatalf("recovery did not clean journal")
	}
}

func TestRecoverRollsBackInReverseAndSkipsAlreadyRestoredSteps(t *testing.T) {
	first := installJournalStep("one", StepApplied)
	second := installJournalStep("two", StepPrepared)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, first, second)
	fixture.workspace.links[first.Location] = stateOf(first.After, first.Parent)
	fixture.workspace.links[second.Location] = stateOf(second.Before, second.Parent)

	_, err := fixture.executor().Recover()

	if err != nil {
		t.Fatalf("recover: %v", err)
	}
	if len(fixture.workspace.writes) != 1 || fixture.workspace.writes[0] != "one:" {
		t.Fatalf("recovery writes = %#v", fixture.workspace.writes)
	}
	assertAbsent(t, fixture.workspace, "one", "two")
}

func TestRecoverLeavesJournalWhenAfterImageDoesNotMatch(t *testing.T) {
	step := installJournalStep("one", StepApplied)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	fixture.workspace.links[step.Location] = linkState("foreign/target")

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "after-image mismatch") {
		t.Fatalf("expected after-image mismatch, got %v", err)
	}
	if fixture.store.journal == nil || fixture.store.cleanupCalls != 0 {
		t.Fatal("unsafe recovery removed journal")
	}
	if fixture.workspace.writeCount() != 0 {
		t.Fatal("unsafe recovery changed workspace")
	}
}

func TestRecoverPreservesSameTargetReplacementWithDifferentIdentity(t *testing.T) {
	step := installJournalStep("one", StepApplied)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	replacement := stateOf(step.After, step.Parent)
	replacement.Entry.Inode++
	fixture.workspace.links[step.Location] = replacement

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "after-image mismatch") {
		t.Fatalf("expected after-image mismatch, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || fixture.store.cleanupCalls != 0 {
		t.Fatal("same-target replacement was mutated")
	}
}

func TestRecoverFailsClosedForPreparedInstallWithoutPublishedIdentity(t *testing.T) {
	step := installJournalStep("one", StepPrepared)
	step.After.Entry = FileIdentity{}
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	fixture.workspace.links[step.Location] = linkState(step.After.RawTarget)

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "after-image mismatch") {
		t.Fatalf("expected after-image mismatch, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || fixture.store.cleanupCalls != 0 {
		t.Fatal("unconfirmed prepared install was mutated")
	}
}

func TestRecoverCommittedJournalOnlyCleansAndCanRetry(t *testing.T) {
	step := installJournalStep("one", StepApplied)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionCommitted, step)
	fixture.workspace.links[step.Location] = stateOf(step.After, step.Parent)
	fixture.store.cleanupErr = errCleanup

	_, firstErr := fixture.executor().Recover()
	fixture.store.cleanupErr = nil
	_, secondErr := fixture.executor().Recover()
	_, thirdErr := fixture.executor().Recover()

	if firstErr == nil || !strings.Contains(firstErr.Error(), "cleanup committed journal") {
		t.Fatalf("expected cleanup error, got %v", firstErr)
	}
	if secondErr != nil || thirdErr != nil {
		t.Fatalf("idempotent recovery errors: second=%v third=%v", secondErr, thirdErr)
	}
	if fixture.workspace.writeCount() != 0 || !fixture.workspace.links[step.Location].Exists {
		t.Fatal("committed recovery mutated installed link")
	}
	if fixture.store.journal != nil || fixture.store.cleanupCalls != 2 {
		t.Fatalf("cleanup calls=%d journal=%#v", fixture.store.cleanupCalls, fixture.store.journal)
	}
}

func TestRecoverRejectsInvalidAndOverlappingJournalLocations(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*Journal)
	}{
		{name: "invalid status", mutate: func(journal *Journal) { journal.Status = "unknown" }},
		{name: "empty release", mutate: func(journal *Journal) { journal.Release.ID = "" }},
		{name: "invalid digest", mutate: func(journal *Journal) { journal.Release.IndexSHA256 = "ABC" }},
		{name: "duplicate desired", mutate: func(journal *Journal) {
			journal.Desired = []domain.ComponentID{"codex", "codex"}
		}},
		{name: "invalid path", mutate: func(journal *Journal) { journal.Steps[0].Location.Path = "../escape" }},
		{name: "invalid raw target", mutate: func(journal *Journal) { journal.Steps[0].After.RawTarget = "bad\nlink" }},
		{name: "invalid parent", mutate: func(journal *Journal) { journal.Steps[0].Parent.Inode = 0 }},
		{name: "partial entry identity", mutate: func(journal *Journal) {
			journal.Steps[0].After.Entry.Device = 0
		}},
		{name: "duplicate location", mutate: func(journal *Journal) {
			journal.Steps = append(journal.Steps, journal.Steps[0])
		}},
		{name: "overlapping location", mutate: func(journal *Journal) {
			child := installJournalStep("one/child", StepApplied)
			journal.Steps = append(journal.Steps, child)
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			fixture.store.journal = journalWith(TransactionInProgress, installJournalStep("one", StepApplied))
			test.mutate(fixture.store.journal)

			_, err := fixture.executor().Recover()

			if err == nil || !strings.Contains(err.Error(), "validate transaction journal") {
				t.Fatalf("expected validation error, got %v", err)
			}
			if fixture.workspace.writeCount() != 0 || fixture.store.cleanupCalls != 0 {
				t.Fatal("invalid journal caused mutation or cleanup")
			}
		})
	}
}

func journalWith(status TransactionStatus, steps ...JournalMutation) *Journal {
	return &Journal{
		Release: ReleaseIdentity{ID: "release", IndexSHA256: testDigest("digest")},
		Desired: []domain.ComponentID{"codex"},
		Status:  status,
		Steps:   append([]JournalMutation(nil), steps...),
	}
}

func installJournalStep(path domain.ArtifactPath, state StepState) JournalMutation {
	return JournalMutation{
		Kind:       MutationInstall,
		Location:   testLocation(path),
		SourcePath: domain.ArtifactPath("source/" + string(path)),
		Before:     LinkImage{},
		After: LinkImage{
			Exists: true, RawTarget: "source/" + string(path),
			Entry: FileIdentity{Device: 1, Inode: 2},
		},
		Parent: FileIdentity{Device: 1, Inode: 1},
		State:  state,
	}
}
