package plan_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

func TestPlannerFiltersFeatureArtifactsFromDesiredOperationsAndOwners(t *testing.T) {
	base := catalog.Artifact{
		UnitID:     "codex.instructions",
		Target:     location(domain.RootCodexConfig, "AGENTS.md"),
		SourcePath: "dist/codex/AGENTS.md",
	}
	feedback := catalog.Artifact{
		UnitID:     "codex.harness-feedback",
		Target:     location(domain.RootCodexConfig, "skills/harness-feedback"),
		SourcePath: "dist/codex/harness-feedback",
		Feature:    domain.FeatureHarnessFeedback,
	}
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{base, feedback},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	managedFeedback := domain.Artifact{
		Location:  feedback.Target,
		UnitID:    feedback.UnitID,
		Ownership: domain.OwnershipManagedExact,
	}

	disabled, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{managedFeedback},
		}}},
	})
	if err != nil {
		t.Fatalf("disabled plan: %v", err)
	}
	assertOperations(t, disabled.Operations, []domain.Operation{
		{ComponentID: "codex", UnitID: base.UnitID, Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: base.Target}, SourcePath: base.SourcePath},
		{ComponentID: "codex", UnitID: feedback.UnitID, Kind: domain.OperationRemove, Artifact: managedFeedback},
	})

	enabled, err := plan.New(registry).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{
			Components: []domain.ComponentID{"codex"},
			Features:   []domain.FeatureID{domain.FeatureHarnessFeedback},
		},
	})
	if err != nil {
		t.Fatalf("enabled plan: %v", err)
	}
	assertOperations(t, enabled.Operations, []domain.Operation{
		{ComponentID: "codex", UnitID: base.UnitID, Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: base.Target}, SourcePath: base.SourcePath},
		{ComponentID: "codex", UnitID: feedback.UnitID, Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: feedback.Target}, SourcePath: feedback.SourcePath},
	})
}

func TestPlannerRejectsUnknownAndDuplicateDesiredFeatures(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex",
		Artifacts: []catalog.Artifact{{
			Target:     location(domain.RootCodexConfig, "feedback"),
			SourcePath: "dist/feedback",
			Feature:    domain.FeatureHarnessFeedback,
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	tests := []struct {
		name     string
		features []domain.FeatureID
		message  string
	}{
		{name: "unknown", features: []domain.FeatureID{"other"}, message: "unknown feature"},
		{name: "duplicate", features: []domain.FeatureID{domain.FeatureHarnessFeedback, domain.FeatureHarnessFeedback}, message: "duplicate feature"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := plan.New(registry).Plan(domain.PlanRequest{
				Desired: domain.DesiredState{
					Components: []domain.ComponentID{"codex"},
					Features:   test.features,
				},
			})
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("Plan() error = %v, want %q", err, test.message)
			}
		})
	}
}
