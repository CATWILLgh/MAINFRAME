package executor

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestRecoverStagesPreparedMutationBeforeIdempotentRollback(t *testing.T) {
	step := installJournalStep("one", StepPrepared)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)

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
	first := installJournalStep("one", StepPublished)
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
	step := installJournalStep("one", StepPublished)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	fixture.workspace.links[step.Location] = linkState("foreign/target")

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "identity mismatch") {
		t.Fatalf("expected identity mismatch, got %v", err)
	}
	if fixture.store.journal == nil || fixture.store.cleanupCalls != 0 {
		t.Fatal("unsafe recovery removed journal")
	}
	if fixture.workspace.writeCount() != 0 {
		t.Fatal("unsafe recovery changed workspace")
	}
}

func TestRecoverPreservesSameTargetReplacementWithDifferentIdentity(t *testing.T) {
	step := installJournalStep("one", StepPublished)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	replacement := stateOf(step.After, step.Parent)
	replacement.Entry.Inode++
	fixture.workspace.links[step.Location] = replacement

	_, err := fixture.executor().Recover()

	if err == nil || !strings.Contains(err.Error(), "identity mismatch") {
		t.Fatalf("expected identity mismatch, got %v", err)
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

	if err == nil || !strings.Contains(err.Error(), "identity mismatch") {
		t.Fatalf("expected identity mismatch, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || fixture.store.cleanupCalls != 0 {
		t.Fatal("unconfirmed prepared install was mutated")
	}
}

func TestRecoverCommittedJournalOnlyCleansAndCanRetry(t *testing.T) {
	step := installJournalStep("one", StepPublished)
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
	for _, test := range invalidJournalCases() {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			fixture.store.journal = journalWith(TransactionInProgress, installJournalStep("one", StepPublished))
			test.mutate(fixture.store.journal)

			_, err := fixture.executor().Recover()

			if err == nil || !strings.Contains(err.Error(), "validate") {
				t.Fatalf("expected validation error, got %v", err)
			}
			if fixture.workspace.filesystemCalls() != 0 || fixture.store.cleanupCalls != 0 {
				t.Fatal("invalid journal caused mutation or cleanup")
			}
		})
	}
}

func invalidJournalCases() []struct {
	name   string
	mutate func(*Journal)
} {
	return []struct {
		name   string
		mutate func(*Journal)
	}{
		{name: "invalid status", mutate: func(journal *Journal) { journal.Status = "unknown" }},
		{name: "empty release", mutate: func(journal *Journal) { journal.Release.ID = "" }},
		{name: "invalid digest", mutate: func(journal *Journal) { journal.Release.IndexSHA256 = "ABC" }},
		{name: "duplicate desired", mutate: func(journal *Journal) {
			journal.Desired = []domain.ComponentID{"codex", "codex"}
		}},
		{name: "changed root anchor", mutate: func(journal *Journal) {
			journal.Roots[0].AnchorPath = "/tmp"
		}},
		{name: "changed root path", mutate: func(journal *Journal) {
			journal.Roots[0].RootPath = ".other"
		}},
		{name: "invalid path", mutate: func(journal *Journal) { journal.Steps[0].Location.Path = "../escape" }},
		{name: "invalid raw target", mutate: func(journal *Journal) { journal.Steps[0].After.RawTarget = "bad\nlink" }},
		{name: "invalid parent", mutate: func(journal *Journal) { journal.Steps[0].Parent.Inode = 0 }},
		{name: "unsafe private name", mutate: func(journal *Journal) {
			journal.Steps[0].Private.Name = "../escape"
		}},
		{name: "partial private identity", mutate: func(journal *Journal) {
			journal.Steps[0].Private.Identity.Device = 0
		}},
		{name: "wrong staged name", mutate: func(journal *Journal) {
			journal.Steps[0].StagedName = "other"
		}},
		{name: "wrong retained name", mutate: func(journal *Journal) {
			journal.Steps[0].RetainedName = "retained"
		}},
		{name: "invalid phase", mutate: func(journal *Journal) {
			journal.Steps[0].Phase = "unknown"
		}},
		{name: "staged identity mismatch", mutate: func(journal *Journal) {
			journal.Steps[0].StagedIdentity.Inode++
		}},
		{name: "partial entry identity", mutate: func(journal *Journal) {
			journal.Steps[0].After.Entry.Device = 0
		}},
		{name: "duplicate location", mutate: func(journal *Journal) {
			journal.Steps = append(journal.Steps, journal.Steps[0])
		}},
		{name: "overlapping location", mutate: func(journal *Journal) {
			child := installJournalStep("one/child", StepPublished)
			journal.Steps = append(journal.Steps, child)
		}},
	}
}

func journalWith(status TransactionStatus, steps ...JournalMutation) *Journal {
	operations := make([]domain.Operation, 0, len(steps))
	roots := make([]RootSnapshot, 0, 1)
	if len(steps) > 0 {
		roots = append(roots, RootSnapshot{
			Root:           domain.RootCodexConfig,
			AnchorPath:     "/home/user",
			AnchorIdentity: FileIdentity{Device: 1, Inode: 1},
			RootPath:       ".codex-config",
		})
	}
	for _, step := range steps {
		operations = append(operations, domain.Operation{
			ComponentID: "codex",
			Kind:        domain.OperationInstall,
			Artifact:    domain.Artifact{Location: step.Location},
			SourcePath:  step.SourcePath,
		})
	}
	return &Journal{
		SchemaVersion: CurrentJournalSchemaVersion,
		Release:       ReleaseIdentity{ID: "release", IndexSHA256: testDigest("digest")},
		Desired:       []domain.ComponentID{"codex"},
		Status:        status,
		Plan:          domain.Plan{Operations: operations},
		Roots:         roots,
		Steps:         append([]JournalMutation(nil), steps...),
	}
}

func installJournalStep(path domain.ArtifactPath, phase StepPhase) JournalMutation {
	step := JournalMutation{
		Kind:       MutationInstall,
		Location:   testLocation(path),
		SourcePath: domain.ArtifactPath("source/" + string(path)),
		Before:     LinkImage{},
		After:      LinkImage{Exists: true, RawTarget: "source/" + string(path)},
		Parent:     FileIdentity{Device: 1, Inode: 1},
		Private: PrivateDirectory{
			Name:     ".mainframe-" + testDigest(string(path))[:32],
			Identity: FileIdentity{Device: 1, Inode: 10},
		},
		StagedName: "staged",
		Phase:      phase,
	}
	if phase != StepPrepared {
		step.StagedIdentity = FileIdentity{Device: 1, Inode: 2}
	}
	if phase == StepPublished {
		step.After.Entry = step.StagedIdentity
	}
	return step
}
