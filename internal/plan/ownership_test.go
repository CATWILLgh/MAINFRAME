package plan_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

func TestPlannerReplacesClaimBackedPreviousRelease(t *testing.T) {
	target := location(domain.RootCodexConfig, "AGENTS.md")
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{{
			UnitID: "codex.instructions", Target: target, SourcePath: "dist/codex/AGENTS.md",
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	previous := domain.Artifact{
		Location: target, UnitID: "codex.instructions",
		Ownership: domain.OwnershipManagedPrevious, RawTarget: "/releases/old/AGENTS.md",
		LinkDevice: 1, LinkInode: 2,
	}
	got, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired:  domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{previous}}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := domain.Operation{
		ComponentID: "codex", UnitID: "codex.instructions", Kind: domain.OperationReplace,
		Artifact: previous, SourcePath: "dist/codex/AGENTS.md",
	}
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func TestPlannerAdoptsExactUnclaimedCurrentRelease(t *testing.T) {
	target := location(domain.RootCodexConfig, "AGENTS.md")
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{{
			UnitID: "codex.instructions", Target: target, SourcePath: "dist/codex/AGENTS.md",
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	adoptable := domain.Artifact{
		Location: target, UnitID: "codex.instructions",
		Ownership: domain.OwnershipExactAdoptable, RawTarget: "/releases/current/AGENTS.md",
		LinkDevice: 1, LinkInode: 2,
	}
	got, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{adoptable},
		}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := domain.Operation{
		ComponentID: "codex", UnitID: "codex.instructions",
		Kind: domain.OperationAdopt, Artifact: adoptable,
	}
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func TestPlannerRemovesOrRelinquishesClaimWithoutCurrentCatalogUnit(t *testing.T) {
	registry, err := catalog.New(nil)
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	tests := []struct {
		name   string
		status domain.OwnershipStatus
		kind   domain.OperationKind
	}{
		{name: "exact dangling link", status: domain.OwnershipManagedPrevious, kind: domain.OperationRemove},
		{name: "changed target", status: domain.OwnershipManagedDrifted, kind: domain.OperationRelinquish},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			artifact := domain.Artifact{
				Location: location(domain.RootCodexConfig, "retired"), UnitID: "retired.link",
				Ownership: test.status, RawTarget: "/releases/old/retired",
				LinkDevice: 4, LinkInode: 5,
			}
			got, err := plan.New(registry).Plan(domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "retired", Artifacts: []domain.Artifact{artifact}}}}})
			if err != nil {
				t.Fatalf("plan: %v", err)
			}
			want := domain.Operation{ComponentID: "retired", UnitID: "retired.link", Kind: test.kind, Artifact: artifact}
			assertOperations(t, got.Operations, []domain.Operation{want})
		})
	}
}

func TestPlannerReinstallsOrRelinquishesMissingClaim(t *testing.T) {
	target := location(domain.RootCodexConfig, "AGENTS.md")
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{{
			UnitID: "codex.instructions", Target: target, SourcePath: "dist/codex/AGENTS.md",
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	missing := domain.Artifact{
		Location: target, UnitID: "codex.instructions",
		Ownership: domain.OwnershipManagedMissing, RawTarget: "/releases/old/AGENTS.md",
	}
	observed := domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: "codex", Artifacts: []domain.Artifact{missing},
	}}}

	reinstall, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired:  domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: observed,
	})
	if err != nil {
		t.Fatalf("plan reinstall: %v", err)
	}
	assertOperations(t, reinstall.Operations, []domain.Operation{{
		ComponentID: "codex", UnitID: "codex.instructions", Kind: domain.OperationInstall,
		Artifact: missing, SourcePath: "dist/codex/AGENTS.md",
	}})

	relinquish, err := plan.New(registry).Plan(domain.PlanRequest{Observed: observed})
	if err != nil {
		t.Fatalf("plan relinquish: %v", err)
	}
	assertOperations(t, relinquish.Operations, []domain.Operation{{
		ComponentID: "codex", UnitID: "codex.instructions",
		Kind: domain.OperationRelinquish, Artifact: missing,
	}})
}
