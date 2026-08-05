package lifecycle

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPlanPreservesOmittedUnmanagedComponents(t *testing.T) {
	statuses := []domain.OwnershipStatus{
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipExactAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}
	for _, status := range statuses {
		t.Run(string(status), func(t *testing.T) {
			service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{{
				ID: domain.ComponentCodex,
				Artifacts: []domain.Artifact{
					artifact(domain.RootCodexConfig, "AGENTS.md", status),
				},
			}}})

			plan, err := service.Plan([]domain.ComponentID{domain.ComponentClaudeCode})
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			assertNoComponentOperations(t, plan.Operations, domain.ComponentCodex)
		})
	}
}

func TestPlanStillRemovesOrRelinquishesOmittedManagedComponents(t *testing.T) {
	tests := []struct {
		name      string
		ownership domain.OwnershipStatus
		wantKind  domain.OperationKind
	}{
		{name: "exact", ownership: domain.OwnershipManagedExact, wantKind: domain.OperationRemove},
		{name: "drifted", ownership: domain.OwnershipManagedDrifted, wantKind: domain.OperationRelinquish},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			observed := artifact(domain.RootCodexConfig, "AGENTS.md", test.ownership)
			observed.UnitID = "codex.AGENTS.md"
			service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{{
				ID:        domain.ComponentCodex,
				Artifacts: []domain.Artifact{observed},
			}}})

			plan, err := service.Plan([]domain.ComponentID{domain.ComponentClaudeCode})
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			assertComponentOperation(t, plan.Operations, domain.ComponentCodex, test.wantKind)
		})
	}
}

func TestPlanDoesNotPreserveSelectedUnmanagedComponent(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: domain.ComponentCodex,
		Artifacts: []domain.Artifact{
			artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipForeign),
		},
	}}})

	plan, err := service.Plan([]domain.ComponentID{domain.ComponentCodex})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	assertComponentOperation(t, plan.Operations, domain.ComponentCodex, domain.OperationConflict)
}

func TestPlanTreatsMixedComponentAsManaged(t *testing.T) {
	managed := artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact)
	managed.UnitID = "codex.AGENTS.md"
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: domain.ComponentCodex,
		Artifacts: []domain.Artifact{
			managed,
			artifact(domain.RootCodexConfig, "skills/foreign", domain.OwnershipForeign),
		},
	}}})

	plan, err := service.Plan([]domain.ComponentID{domain.ComponentClaudeCode})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	assertComponentOperation(t, plan.Operations, domain.ComponentCodex, domain.OperationRemove)
	assertNoComponentOperationKind(t, plan.Operations, domain.ComponentCodex, domain.OperationConflict)
}

func TestPlanStillRemovesOmittedManagedInternalComponent(t *testing.T) {
	managed := artifact(domain.RootCommonData, "codex-gates", domain.OwnershipManagedExact)
	managed.UnitID = "codex-gates.bundle"
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{
				artifact(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipForeign),
			},
		},
		{ID: domain.ComponentCodexGates, Artifacts: []domain.Artifact{managed}},
	}})

	plan, err := service.Plan(nil)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	assertNoComponentOperations(t, plan.Operations, domain.ComponentClaudeCode)
	assertComponentOperation(t, plan.Operations, domain.ComponentCodexGates, domain.OperationRemove)
}

func TestPreviewPreservesOnlyUnmanagedAdapterConfiguration(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID:           domain.ComponentClaudeCode,
			Dependencies: []domain.ComponentID{"credential-tools"},
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootClaudeConfig, "CLAUDE.md", "claude/CLAUDE.md"),
			},
		},
		{ID: "credential-tools"},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	resources := []releasecontract.Resource{
		{
			ID: "claude-code.settings", ComponentID: domain.ComponentClaudeCode,
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Target:      domain.Location{Root: domain.RootClaudeConfig, Path: "settings.json"},
			Observation: releasecontract.SupportUnimplemented,
			Apply:       releasecontract.SupportUnimplemented,
		},
		{
			ID: "credential-tools.store", ComponentID: "credential-tools",
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Target:      domain.Location{Root: domain.RootCredentialsConfig, Path: "secrets.env"},
			Observation: releasecontract.SupportUnimplemented,
			Apply:       releasecontract.SupportUnimplemented,
		},
	}
	service, err := NewWithResources(
		model,
		domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{
				artifact(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipForeign),
			},
		}}},
		resources,
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}

	preview, err := service.Preview(PreviewRequest{})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.Configuration.Issues) != 1 ||
		preview.Configuration.Issues[0].ComponentID != "credential-tools" {
		t.Fatalf("configuration issues = %#v", preview.Configuration.Issues)
	}
}

func assertNoComponentOperations(
	t *testing.T,
	operations []domain.Operation,
	componentID domain.ComponentID,
) {
	t.Helper()
	for _, operation := range operations {
		if operation.ComponentID == componentID {
			t.Fatalf("operation = %#v, want component preserved", operation)
		}
	}
}

func assertComponentOperation(
	t *testing.T,
	operations []domain.Operation,
	componentID domain.ComponentID,
	kind domain.OperationKind,
) {
	t.Helper()
	for _, operation := range operations {
		if operation.ComponentID == componentID && operation.Kind == kind {
			return
		}
	}
	t.Fatalf("operations = %#v, want %q for %q", operations, kind, componentID)
}

func assertNoComponentOperationKind(
	t *testing.T,
	operations []domain.Operation,
	componentID domain.ComponentID,
	kind domain.OperationKind,
) {
	t.Helper()
	for _, operation := range operations {
		if operation.ComponentID == componentID && operation.Kind == kind {
			t.Fatalf("operation = %#v, want kind omitted", operation)
		}
	}
}
