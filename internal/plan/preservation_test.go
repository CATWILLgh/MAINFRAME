package plan_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPlannerPreservesObservedComponentWithoutRepairOrRemoval(t *testing.T) {
	statuses := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}
	for _, status := range statuses {
		t.Run(string(status), func(t *testing.T) {
			request := domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
				ID: "codex", Artifacts: []domain.Artifact{
					observed(domain.RootCodexConfig, "AGENTS.md", status),
				},
			}}}}
			got, err := newPlanner(t).PlanWithPreservation(request, []domain.ComponentID{"codex"})
			if err != nil {
				t.Fatalf("PlanWithPreservation() error = %v", err)
			}
			if len(got.Operations) != 0 {
				t.Fatalf("operations = %#v, want none", got.Operations)
			}
		})
	}
}

func TestPlannerPreservesDependencyClosureAndSelectedStateWins(t *testing.T) {
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex-gates"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "shared-gate-detectors", Artifacts: []domain.Artifact{
				observed(domain.RootCommonData, "detector", domain.OwnershipManagedDrifted),
			},
		}}},
	}
	got, err := newPlanner(t).PlanWithPreservation(
		request,
		[]domain.ComponentID{"codex-gates"},
	)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	want := operation(
		"shared-gate-detectors",
		domain.OperationConflict,
		observed(domain.RootCommonData, "detector", domain.OwnershipManagedDrifted),
	)
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func TestPlannerPreservedMissingComponentDoesNotGetInstalled(t *testing.T) {
	got, err := newPlanner(t).PlanWithPreservation(
		domain.PlanRequest{},
		[]domain.ComponentID{"codex"},
	)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if len(got.Operations) != 0 {
		t.Fatalf("operations = %#v, want none", got.Operations)
	}
}
