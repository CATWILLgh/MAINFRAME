package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

const writableJournalDigest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func TestWritableFileRelinquishJournalRoundTrip(t *testing.T) {
	location := domain.Location{Root: domain.RootCodexConfig, Path: "agents/local.md"}
	claim := linkownership.Claim{
		UnitID: "codex.agent", ComponentID: "codex", Target: location,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   writableJournalDigest, Mode: writableFileMode,
		ReleaseID: "release", IndexSHA256: writableJournalDigest,
	}
	journal := Journal{
		Release: ReleaseIdentity{ID: "release", IndexSHA256: writableJournalDigest},
		Desired: []domain.ComponentID{}, Status: TransactionInProgress,
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: "codex", UnitID: "codex.agent", Kind: domain.OperationRelinquish,
			Artifact: domain.Artifact{
				Location: location, UnitID: "codex.agent",
				Materialization: domain.MaterializationWritableFile,
				Ownership:       domain.OwnershipManagedDrifted,
			},
		}}},
		Steps: []JournalMutation{{
			ComponentID: "codex", UnitID: "codex.agent", Kind: MutationRelinquish,
			Location: location, Materialization: domain.MaterializationWritableFile,
			Phase: StepPrepared, ClaimBefore: &claim, ClaimPhase: ClaimPrepared,
		}},
	}
	payload, err := encodeJournal(journal)
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	decoded, err := decodeJournal(payload)
	if err != nil {
		t.Fatalf("decodeJournal() error = %v", err)
	}
	if decoded.Steps[0].Materialization != domain.MaterializationWritableFile {
		t.Fatalf("decoded step = %#v", decoded.Steps[0])
	}
}
