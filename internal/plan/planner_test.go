package plan_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

func TestPlannerRemovesOnlyExactArtifactsOfKnownUndesiredComponents(t *testing.T) {
	planner := newPlanner(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"claude-code"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{
			{ID: "claude-code", Artifacts: []domain.Artifact{observed(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipManagedExact)}},
			{ID: "codex", Artifacts: []domain.Artifact{
				observed(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact),
				observed(domain.RootCodexConfig, "config.toml", domain.OwnershipManagedDrifted),
				observed(domain.RootCodexConfig, "legacy.md", domain.OwnershipLegacyAdoptable),
				observed(domain.RootCodexConfig, "foreign.md", domain.OwnershipForeign),
				observed(domain.RootCodexConfig, "conflict.md", domain.OwnershipConflict),
			}},
			{ID: "retired", Artifacts: []domain.Artifact{observed(domain.RootHome, "legacy/exact", domain.OwnershipManagedExact)}},
		}},
	}
	got, err := planner.Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "config.toml", domain.OwnershipManagedDrifted)),
		operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "conflict.md", domain.OwnershipConflict)),
		operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "foreign.md", domain.OwnershipForeign)),
		operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "legacy.md", domain.OwnershipLegacyAdoptable)),
		operation("codex", domain.OperationRemove, observed(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact)),
		operation("retired", domain.OperationConflict, observed(domain.RootHome, "legacy/exact", domain.OwnershipManagedExact)),
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerSortsByComponentKindAndLocation(t *testing.T) {
	request := domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: "codex", Artifacts: []domain.Artifact{
			observed(domain.RootHome, "z", domain.OwnershipManagedExact),
			observed(domain.RootCodexConfig, "b", domain.OwnershipManagedExact),
			observed(domain.RootCodexConfig, "a", domain.OwnershipForeign),
		},
	}}}}
	got, err := newPlanner(t).Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "a", domain.OwnershipForeign)),
		operation("codex", domain.OperationRemove, observed(domain.RootCodexConfig, "b", domain.OwnershipManagedExact)),
		operation("codex", domain.OperationRemove, observed(domain.RootHome, "z", domain.OwnershipManagedExact)),
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerInstallsDesiredDependencyArtifactsWithSources(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{ID: "gates", Dependencies: []domain.ComponentID{"detectors"}, Artifacts: []catalog.Artifact{expected(domain.RootCodexConfig, "gates", "dist/gates")}},
		{ID: "detectors", Artifacts: []catalog.Artifact{expected(domain.RootCommonData, "detectors", "dist/detectors")}},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	got, err := plan.New(registry).Plan(domain.PlanRequest{Desired: domain.DesiredState{Components: []domain.ComponentID{"gates"}}})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		{ComponentID: "detectors", Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: location(domain.RootCommonData, "detectors")}, SourcePath: "dist/detectors"},
		{ComponentID: "gates", Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: location(domain.RootCodexConfig, "gates")}, SourcePath: "dist/gates"},
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerKeepsSamePathUnderDifferentRootsDistinct(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{ID: "codex", Artifacts: []catalog.Artifact{
		expected(domain.RootCodexConfig, "AGENTS.md", "dist/codex/AGENTS.md"),
		expected(domain.RootHome, "AGENTS.md", "dist/home/AGENTS.md"),
	}}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{
			observed(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact),
		}}}},
	}
	got, err := plan.New(registry).Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{{
		ComponentID: "codex", Kind: domain.OperationInstall,
		Artifact: domain.Artifact{Location: location(domain.RootHome, "AGENTS.md")}, SourcePath: "dist/home/AGENTS.md",
	}}
	assertOperations(t, got.Operations, want)
}

func TestPlannerReportsOneConflictWhenObservedOwnerDiffers(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude", Artifacts: []catalog.Artifact{expected(domain.RootCommonData, "shared", "dist/shared")}},
		{ID: "codex"},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"claude"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{
			observed(domain.RootCommonData, "shared", domain.OwnershipManagedExact),
		}}}},
	}
	got, err := plan.New(registry).Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{operation("claude", domain.OperationConflict, observed(domain.RootCommonData, "shared", domain.OwnershipManagedExact))}
	assertOperations(t, got.Operations, want)
}

func TestPlannerClassifiesDesiredArtifactByOwnership(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{ID: "codex", Artifacts: []catalog.Artifact{
		expected(domain.RootCodexConfig, "AGENTS.md", "dist/AGENTS.md"),
	}}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	statuses := []domain.OwnershipStatus{
		domain.OwnershipManagedExact, domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable, domain.OwnershipForeign, domain.OwnershipConflict,
	}
	for _, status := range statuses {
		t.Run(string(status), func(t *testing.T) {
			request := requestWithObserved("codex", location(domain.RootCodexConfig, "AGENTS.md"), status)
			got, err := plan.New(registry).Plan(request)
			if err != nil {
				t.Fatalf("plan: %v", err)
			}
			if status == domain.OwnershipManagedExact && len(got.Operations) != 0 {
				t.Fatalf("exact artifact should be healthy, got %#v", got.Operations)
			}
			if status != domain.OwnershipManagedExact {
				want := operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "AGENTS.md", status))
				assertOperations(t, got.Operations, []domain.Operation{want})
			}
		})
	}
}

func TestPlannerLegacyOnlyObservationIsValidAndNeverRemoved(t *testing.T) {
	request := domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: "codex", Artifacts: []domain.Artifact{observed(domain.RootCodexConfig, "legacy", domain.OwnershipLegacyAdoptable)},
	}}}}
	got, err := newPlanner(t).Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := operation("codex", domain.OperationConflict, observed(domain.RootCodexConfig, "legacy", domain.OwnershipLegacyAdoptable))
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func TestPlannerRejectsDuplicateObservedState(t *testing.T) {
	same := observed(domain.RootCodexConfig, "same", domain.OwnershipManagedExact)
	tests := []struct {
		name       string
		components []domain.ObservedComponent
		message    string
	}{
		{name: "component", components: []domain.ObservedComponent{{ID: "codex"}, {ID: "codex"}}, message: "duplicate observed component"},
		{name: "location within", components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{same, same}}}, message: "duplicate observed artifact location"},
		{name: "location across", components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{same}}, {ID: "claude", Artifacts: []domain.Artifact{same}}}, message: "duplicate observed artifact location"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := newPlanner(t).Plan(domain.PlanRequest{Observed: domain.ObservedState{Components: tt.components}})
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestPlannerAllowsSameObservedPathUnderDifferentRoots(t *testing.T) {
	request := domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{
		observed(domain.RootCodexConfig, "same", domain.OwnershipManagedExact),
		observed(domain.RootHome, "same", domain.OwnershipManagedExact),
	}}}}}
	got, err := newPlanner(t).Plan(request)
	if err != nil || len(got.Operations) != 2 {
		t.Fatalf("operations = %#v, error = %v", got.Operations, err)
	}
}

func TestPlannerRejectsInvalidObservedBoundary(t *testing.T) {
	tests := []struct {
		name      string
		component domain.ObservedComponent
		message   string
	}{
		{name: "empty component", component: domain.ObservedComponent{}, message: "component ID"},
		{name: "invalid root", component: domain.ObservedComponent{ID: "codex", Artifacts: []domain.Artifact{{Location: domain.Location{Root: "Invalid", Path: "file"}, Ownership: domain.OwnershipManagedExact}}}, message: "invalid artifact location"},
		{name: "empty path", component: domain.ObservedComponent{ID: "codex", Artifacts: []domain.Artifact{{Location: domain.Location{Root: domain.RootHome}, Ownership: domain.OwnershipManagedExact}}}, message: "invalid artifact location"},
		{name: "invalid ownership", component: domain.ObservedComponent{ID: "codex", Artifacts: []domain.Artifact{{Location: location(domain.RootHome, "file"), Ownership: "unknown"}}}, message: "invalid ownership"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := newPlanner(t).Plan(domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{tt.component}}})
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestCatalogMutationCannotChangeArtifactPlan(t *testing.T) {
	components := []catalog.Component{{ID: "codex", Artifacts: []catalog.Artifact{expected(domain.RootCodexConfig, "original", "dist/original")}}}
	registry, err := catalog.New(components)
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	components[0].Artifacts[0].Target.Path = "changed"
	returned, _ := registry.Component("codex")
	returned.Artifacts[0].SourcePath = "changed"
	got, err := plan.New(registry).Plan(domain.PlanRequest{Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}}})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := domain.Operation{ComponentID: "codex", Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: location(domain.RootCodexConfig, "original")}, SourcePath: "dist/original"}
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func newPlanner(t *testing.T) plan.Planner {
	t.Helper()
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude-code", Artifacts: []catalog.Artifact{expected(domain.RootClaudeConfig, "CLAUDE.md", "dist/CLAUDE.md")}},
		{ID: "codex"},
		{ID: "codex-gates", Dependencies: []domain.ComponentID{"shared-gate-detectors"}},
		{ID: "shared-gate-detectors", Artifacts: []catalog.Artifact{expected(domain.RootCommonData, "detector", "dist/detector")}},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	return plan.New(registry)
}

func expected(root domain.RootID, target, source domain.ArtifactPath) catalog.Artifact {
	return catalog.Artifact{Target: location(root, target), SourcePath: source}
}

func observed(root domain.RootID, path domain.ArtifactPath, status domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{Location: location(root, path), Ownership: status}
}

func location(root domain.RootID, path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: root, Path: path}
}

func operation(id domain.ComponentID, kind domain.OperationKind, artifact domain.Artifact) domain.Operation {
	return domain.Operation{ComponentID: id, Kind: kind, Artifact: artifact}
}

func requestWithObserved(id domain.ComponentID, target domain.Location, status domain.OwnershipStatus) domain.PlanRequest {
	return domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{id}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: id, Artifacts: []domain.Artifact{{Location: target, Ownership: status}},
		}}},
	}
}

func assertOperations(t *testing.T, got, want []domain.Operation) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("operation count = %d, want %d\n got: %#v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("operation[%d] = %#v, want %#v", i, got[i], want[i])
		}
	}
}
