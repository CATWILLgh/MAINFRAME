package executor

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestValidateOperationsRejectsSemanticPreservation(t *testing.T) {
	err := validateOperations([]domain.Operation{{
		ComponentID: "codex", UnitID: "codex.agent",
		Kind: domain.OperationPreserve,
		Artifact: domain.Artifact{
			Location: domain.Location{Root: domain.RootCodexConfig, Path: "agents/agent.md"},
			UnitID:   "codex.agent", Ownership: domain.OwnershipManagedDrifted,
			Materialization: domain.MaterializationWritableFile,
		},
	}})
	if err == nil || !strings.Contains(err.Error(), "unsupported operation") {
		t.Fatalf("validateOperations() error = %v, want unsupported operation", err)
	}
}
