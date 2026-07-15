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
			{ID: "claude-code", Artifacts: []domain.Artifact{
				{Path: ".claude/CLAUDE.md", Ownership: domain.OwnershipManagedExact},
			}},
			{ID: "codex", Artifacts: []domain.Artifact{
				{Path: ".codex/AGENTS.md", Ownership: domain.OwnershipManagedExact},
				{Path: ".codex/config.toml", Ownership: domain.OwnershipManagedDrifted},
				{Path: ".codex/legacy.md", Ownership: domain.OwnershipLegacyAdoptable},
				{Path: ".codex/foreign.md", Ownership: domain.OwnershipForeign},
				{Path: ".codex/conflict.md", Ownership: domain.OwnershipConflict},
				{Path: ".codex/old-layout.rules", Ownership: domain.OwnershipManagedExact},
			}},
			{ID: "retired-plugin", Artifacts: []domain.Artifact{
				{Path: ".legacy/exact-but-unattributed", Ownership: domain.OwnershipManagedExact},
			}},
		}},
	}

	got, err := planner.Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: ".codex/config.toml", Ownership: domain.OwnershipManagedDrifted}},
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: ".codex/conflict.md", Ownership: domain.OwnershipConflict}},
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: ".codex/foreign.md", Ownership: domain.OwnershipForeign}},
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: ".codex/legacy.md", Ownership: domain.OwnershipLegacyAdoptable}},
		{ComponentID: "codex", Kind: domain.OperationRemove, Artifact: domain.Artifact{Path: ".codex/AGENTS.md", Ownership: domain.OwnershipManagedExact}},
		{ComponentID: "codex", Kind: domain.OperationRemove, Artifact: domain.Artifact{Path: ".codex/old-layout.rules", Ownership: domain.OwnershipManagedExact}},
		{ComponentID: "retired-plugin", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: ".legacy/exact-but-unattributed", Ownership: domain.OwnershipManagedExact}},
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerSortsByComponentKindAndArtifactPath(t *testing.T) {
	planner := newPlanner(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{
			{ID: "codex", Artifacts: []domain.Artifact{
				{Path: "z", Ownership: domain.OwnershipManagedExact},
				{Path: "a", Ownership: domain.OwnershipForeign},
				{Path: "b", Ownership: domain.OwnershipManagedExact},
			}},
		}},
	}

	got, err := planner.Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: "a", Ownership: domain.OwnershipForeign}},
		{ComponentID: "codex", Kind: domain.OperationRemove, Artifact: domain.Artifact{Path: "b", Ownership: domain.OwnershipManagedExact}},
		{ComponentID: "codex", Kind: domain.OperationRemove, Artifact: domain.Artifact{Path: "z", Ownership: domain.OwnershipManagedExact}},
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerUsesDesiredDependencyClosure(t *testing.T) {
	planner := newPlanner(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex-gates"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{
			{ID: "shared-gate-detectors", Artifacts: []domain.Artifact{{Path: "detector", Ownership: domain.OwnershipManagedExact}}},
		}},
	}

	got, err := planner.Plan(request)
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	if len(got.Operations) != 0 {
		t.Fatalf("dependency artifact should be retained, got %v", got.Operations)
	}
}

func TestPlannerInstallsArtifactsForDesiredDependencyClosure(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{
			ID:           "codex-gates",
			Dependencies: []domain.ComponentID{"shared-gate-detectors"},
			Artifacts:    []domain.Artifact{{Path: ".codex/gates"}},
		},
		{ID: "shared-gate-detectors", Artifacts: []domain.Artifact{{Path: ".local/share/mainframe/detectors"}}},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}

	got, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex-gates"}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		{ComponentID: "codex-gates", Kind: domain.OperationInstall, Artifact: domain.Artifact{Path: ".codex/gates"}},
		{ComponentID: "shared-gate-detectors", Kind: domain.OperationInstall, Artifact: domain.Artifact{Path: ".local/share/mainframe/detectors"}},
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerReportsOneConflictWhenObservedOwnerDiffers(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude-code", Artifacts: []domain.Artifact{{Path: "shared"}}},
		{ID: "codex"},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}

	got, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"claude-code"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{{Path: "shared", Ownership: domain.OwnershipManagedExact}},
		}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{{
		ComponentID: "claude-code",
		Kind:        domain.OperationConflict,
		Artifact:    domain.Artifact{Path: "shared", Ownership: domain.OwnershipManagedExact},
	}}
	assertOperations(t, got.Operations, want)
}

func TestPlannerReconcilesStaleArtifactsOfDesiredComponent(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []domain.Artifact{{Path: "current"}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}

	got, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex",
			Artifacts: []domain.Artifact{
				{Path: "current", Ownership: domain.OwnershipManagedExact},
				{Path: "stale-exact", Ownership: domain.OwnershipManagedExact},
				{Path: "stale-drifted", Ownership: domain.OwnershipManagedDrifted},
			},
		}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Path: "stale-drifted", Ownership: domain.OwnershipManagedDrifted}},
		{ComponentID: "codex", Kind: domain.OperationRemove, Artifact: domain.Artifact{Path: "stale-exact", Ownership: domain.OwnershipManagedExact}},
	}
	assertOperations(t, got.Operations, want)
}

func TestPlannerClassifiesDesiredArtifactByOwnership(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []domain.Artifact{{Path: ".codex/AGENTS.md"}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	planner := plan.New(registry)
	statuses := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}
	for _, status := range statuses {
		t.Run(string(status), func(t *testing.T) {
			request := requestWithObservedArtifact("codex", ".codex/AGENTS.md", status)
			got, err := planner.Plan(request)
			if err != nil {
				t.Fatalf("plan: %v", err)
			}
			if status == domain.OwnershipManagedExact && len(got.Operations) != 0 {
				t.Fatalf("exact artifact should be healthy, got %#v", got.Operations)
			}
			if status != domain.OwnershipManagedExact {
				assertDesiredConflict(t, got, status)
			}
		})
	}
}

func TestPlannerRejectsDuplicateObservedState(t *testing.T) {
	tests := []struct {
		name       string
		components []domain.ObservedComponent
		message    string
	}{
		{name: "component ID", components: []domain.ObservedComponent{{ID: "codex"}, {ID: "codex"}}, message: "duplicate observed component"},
		{name: "path within component", components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{
			{Path: "same", Ownership: domain.OwnershipManagedExact}, {Path: "same", Ownership: domain.OwnershipForeign},
		}}}, message: "duplicate observed artifact path"},
		{name: "path across components", components: []domain.ObservedComponent{
			{ID: "codex", Artifacts: []domain.Artifact{{Path: "same", Ownership: domain.OwnershipManagedExact}}},
			{ID: "claude-code", Artifacts: []domain.Artifact{{Path: "same", Ownership: domain.OwnershipManagedExact}}},
		}, message: "duplicate observed artifact path"},
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

func TestPlannerRejectsEmptyObservedIdentifiers(t *testing.T) {
	tests := []struct {
		name       string
		components []domain.ObservedComponent
		message    string
	}{
		{name: "component ID", components: []domain.ObservedComponent{{ID: ""}}, message: "component ID must not be empty"},
		{name: "artifact path", components: []domain.ObservedComponent{{
			ID: "codex",
			Artifacts: []domain.Artifact{{
				Path:      "",
				Ownership: domain.OwnershipManagedExact,
			}},
		}}, message: "artifact path must not be empty"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := newPlanner(t).Plan(domain.PlanRequest{
				Observed: domain.ObservedState{Components: test.components},
			})
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("expected %q error, got %v", test.message, err)
			}
		})
	}
}

func TestPlannerRejectsUnsafeObservedPaths(t *testing.T) {
	for _, artifactPath := range []string{"/absolute", "../outside", "a/../b", "a//b", ".", `a\b`, "line\nbreak"} {
		t.Run(artifactPath, func(t *testing.T) {
			_, err := newPlanner(t).Plan(domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
				ID: "codex",
				Artifacts: []domain.Artifact{{
					Path:      domain.ArtifactPath(artifactPath),
					Ownership: domain.OwnershipManagedExact,
				}},
			}}}})
			if err == nil || !strings.Contains(err.Error(), "invalid artifact path") {
				t.Fatalf("expected invalid artifact path error, got %v", err)
			}
		})
	}
}

func TestPlannerRejectsInvalidObservedOwnership(t *testing.T) {
	for _, status := range []domain.OwnershipStatus{"", "unknown"} {
		t.Run(string(status), func(t *testing.T) {
			request := requestWithObservedArtifact("codex", "artifact", status)
			_, err := newPlanner(t).Plan(request)
			if err == nil || !strings.Contains(err.Error(), "invalid ownership") {
				t.Fatalf("expected invalid ownership error, got %v", err)
			}
		})
	}
}

func TestCatalogMutationCannotChangeArtifactPlan(t *testing.T) {
	components := []catalog.Component{{ID: "codex", Artifacts: []domain.Artifact{{Path: "original"}}}}
	registry, err := catalog.New(components)
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	components[0].Artifacts[0].Path = "input-mutation"
	returned, _ := registry.Component("codex")
	returned.Artifacts[0].Path = "return-mutation"

	got, err := plan.New(registry).Plan(domain.PlanRequest{Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}}})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	want := []domain.Operation{{ComponentID: "codex", Kind: domain.OperationInstall, Artifact: domain.Artifact{Path: "original"}}}
	assertOperations(t, got.Operations, want)
}

func requestWithObservedArtifact(id domain.ComponentID, path domain.ArtifactPath, status domain.OwnershipStatus) domain.PlanRequest {
	return domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{id}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: id, Artifacts: []domain.Artifact{{Path: path, Ownership: status}},
		}}},
	}
}

func assertDesiredConflict(t *testing.T, got domain.Plan, status domain.OwnershipStatus) {
	t.Helper()
	want := domain.Operation{
		ComponentID: "codex",
		Kind:        domain.OperationConflict,
		Artifact:    domain.Artifact{Path: ".codex/AGENTS.md", Ownership: status},
	}
	assertOperations(t, got.Operations, []domain.Operation{want})
}

func newPlanner(t *testing.T) plan.Planner {
	t.Helper()
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude-code", Artifacts: []domain.Artifact{{Path: ".claude/CLAUDE.md"}}},
		{ID: "codex"},
		{ID: "codex-gates", Dependencies: []domain.ComponentID{"shared-gate-detectors"}},
		{ID: "shared-gate-detectors", Artifacts: []domain.Artifact{{Path: "detector"}}},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	return plan.New(registry)
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
