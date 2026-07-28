package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestValidateOperationsAcceptsPortableUnitID(t *testing.T) {
	operation := claimedInstall("agents/decision-reviewer.md", "dist/agent.md")
	operation.UnitID = "opencode.agents/decision-reviewer.md"
	operation.ComponentID = domain.ComponentOpenCode
	operation.Artifact.UnitID = operation.UnitID
	operation.Artifact.Location.Root = domain.RootOpenCodeConfig

	if err := validateOperations([]domain.Operation{operation}); err != nil {
		t.Fatalf("validateOperations() error = %v", err)
	}
}

func TestValidateStepClaimsAcceptsPortableUnitID(t *testing.T) {
	unitID := "opencode.agents/decision-reviewer.md"
	claim := linkownership.Claim{
		UnitID: unitID, ComponentID: domain.ComponentOpenCode,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "agents/decision-reviewer.md",
		},
		RawTarget:   "/release/opencode/agents/decision-reviewer.md",
		ReleaseID:   "release-one",
		IndexSHA256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
	}
	step := JournalMutation{
		UnitID: unitID, ComponentID: domain.ComponentOpenCode,
		Location: claim.Target, Kind: MutationInstall,
		ClaimAfter: &claim, ClaimPhase: ClaimPrepared,
	}

	if err := validateStepClaims(step); err != nil {
		t.Fatalf("validateStepClaims() error = %v", err)
	}
}
