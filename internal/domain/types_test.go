package domain_test

import (
	"encoding/json"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPlanJSONContract(t *testing.T) {
	plan := domain.Plan{Operations: []domain.Operation{{
		ComponentID: "codex",
		Kind:        domain.OperationRemove,
		Artifact: domain.Artifact{
			Path:      ".codex/AGENTS.md",
			Ownership: domain.OwnershipManagedExact,
		},
	}}}

	got, err := json.Marshal(plan)
	if err != nil {
		t.Fatalf("marshal plan: %v", err)
	}
	want := `{"operations":[{"component_id":"codex","kind":"remove","artifact":{"path":".codex/AGENTS.md","ownership":"managed_exact"}}]}`
	if string(got) != want {
		t.Fatalf("JSON contract mismatch\nwant: %s\n got: %s", want, got)
	}
}

func TestOnlyManagedExactIsRemovable(t *testing.T) {
	statuses := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}

	for _, status := range statuses {
		want := status == domain.OwnershipManagedExact
		if got := status.Removable(); got != want {
			t.Errorf("Removable(%q) = %v, want %v", status, got, want)
		}
	}
}

func TestOwnershipStatusValidity(t *testing.T) {
	valid := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}
	for _, status := range valid {
		if !status.Valid() {
			t.Errorf("Valid(%q) = false, want true", status)
		}
	}
	for _, status := range []domain.OwnershipStatus{"", "unknown"} {
		if status.Valid() {
			t.Errorf("Valid(%q) = true, want false", status)
		}
	}
}
