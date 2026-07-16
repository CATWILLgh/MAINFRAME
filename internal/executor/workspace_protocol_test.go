package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestInstallJournalsPrivateAndStagedIdentitiesBeforePublish(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err != nil {
		t.Fatalf("apply: %v", err)
	}
	if len(fixture.store.saves) < 4 {
		t.Fatalf("journal saves = %d, want protocol boundaries", len(fixture.store.saves))
	}
	allocated := fixture.store.saves[0].Steps[0]
	if allocated.Private.Name == "" || allocated.Private.Identity != (FileIdentity{}) {
		t.Fatalf("allocated private directory = %#v", allocated.Private)
	}
	prepared := fixture.store.saves[1].Steps[0]
	if !validFileIdentity(prepared.Private.Identity) {
		t.Fatalf("prepared private directory = %#v", prepared.Private)
	}
	staged := fixture.store.saves[2].Steps[0]
	if staged.Phase != StepStaged || !validFileIdentity(staged.StagedIdentity) {
		t.Fatalf("staged mutation = %#v", staged)
	}
	if fixture.workspace.publishSaveCount < 3 {
		t.Fatalf("publish happened before staged identity save %d", fixture.workspace.publishSaveCount)
	}
}

func TestCommittedRecoveryFinalizesBeforeJournalCleanup(t *testing.T) {
	step := installJournalStep("one", StepPublished)
	step.Finalized = false
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionCommitted, step)

	_, err := fixture.executor().Recover()

	if err != nil {
		t.Fatalf("recover: %v", err)
	}
	if fixture.workspace.finalizeCalls != 1 || fixture.workspace.finalizePrivateCalls != 1 {
		t.Fatalf(
			"finalize calls = %d private = %d",
			fixture.workspace.finalizeCalls,
			fixture.workspace.finalizePrivateCalls,
		)
	}
	if fixture.store.cleanupCalls != 1 {
		t.Fatalf("cleanup calls = %d", fixture.store.cleanupCalls)
	}
}
