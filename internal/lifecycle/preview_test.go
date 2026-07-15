package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPreviewTargetsReportManagedAttentionAndAbsent(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{
				artifact(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipManagedExact),
			},
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []domain.Artifact{
				artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipConflict),
			},
		},
	}})

	want := []Target{
		{ID: domain.ComponentClaudeCode, Status: StatusManaged, Selected: true},
		{ID: domain.ComponentCodex, Status: StatusAttention, Selected: true},
		{ID: domain.ComponentOpenCode, Status: StatusAbsent},
	}
	if got := service.Targets(); !reflect.DeepEqual(got, want) {
		t.Fatalf("targets = %#v, want %#v", got, want)
	}
}

func TestPreviewBuildsPlanForVisibleTargets(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentCodex,
			Artifacts: []domain.Artifact{
				artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact),
			},
		},
	}})

	result, err := service.Plan([]domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentOpenCode,
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	wantKinds := map[domain.ComponentID]domain.OperationKind{
		domain.ComponentClaudeCode: domain.OperationInstall,
		domain.ComponentCodex:      domain.OperationRemove,
		domain.ComponentOpenCode:   domain.OperationInstall,
	}
	if len(result.Operations) != len(wantKinds) {
		t.Fatalf("operations = %#v", result.Operations)
	}
	for _, operation := range result.Operations {
		if wantKinds[operation.ComponentID] != operation.Kind {
			t.Fatalf("operation = %#v, want kind %q", operation, wantKinds[operation.ComponentID])
		}
	}
}

func TestPreviewReportsConfigurationInventoryWithoutCallingItManaged(t *testing.T) {
	model := testModel(t)
	service, err := NewWithResources(
		model,
		domain.ObservedState{},
		[]releasecontract.Resource{
			{
				ID:          "claude-code.permissions",
				ComponentID: domain.ComponentClaudeCode,
				Strategy:    releasecontract.StrategyJSONKeyMerge,
				Observation: releasecontract.SupportUnimplemented,
				Apply:       releasecontract.SupportUnimplemented,
			},
		},
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}
	target := service.Targets()[0]
	want := []ConfigurationResource{
		{
			ID:       "claude-code.permissions",
			Strategy: releasecontract.StrategyJSONKeyMerge,
			Status:   ConfigurationNotAssessed,
		},
	}
	if !reflect.DeepEqual(target.Configuration, want) {
		t.Fatalf("configuration = %#v, want %#v", target.Configuration, want)
	}
}

func TestPreviewProjectsDependencyHealthAndConfigurationOntoVisibleTarget(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID:           domain.ComponentClaudeCode,
			Dependencies: []domain.ComponentID{"credential-tools", "mainframe-cli"},
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootClaudeConfig, "CLAUDE.md", "claude/CLAUDE.md"),
			},
		},
		{
			ID: "credential-tools",
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootUserBin, "secret", "common/secret"),
			},
		},
		{
			ID: "mainframe-cli",
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootUserBin, "mainframe", "bin/mainframe"),
			},
		},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	service, err := NewWithResources(
		model,
		domain.ObservedState{Components: []domain.ObservedComponent{
			{
				ID: domain.ComponentClaudeCode,
				Artifacts: []domain.Artifact{
					artifact(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipManagedExact),
				},
			},
			{
				ID: "mainframe-cli",
				Artifacts: []domain.Artifact{
					artifact(domain.RootUserBin, "mainframe", domain.OwnershipManagedExact),
				},
			},
		}},
		[]releasecontract.Resource{
			{
				ID: "claude-code.permissions", ComponentID: domain.ComponentClaudeCode,
				Strategy: releasecontract.StrategyJSONKeyMerge,
			},
			{
				ID: "credential-tools.secrets-store", ComponentID: "credential-tools",
				Strategy: releasecontract.StrategySeedIfAbsent,
			},
		},
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}
	target := service.Targets()[0]
	if target.Status != StatusAttention {
		t.Fatalf("status = %q, want %q", target.Status, StatusAttention)
	}
	wantResources := []ConfigurationResource{
		{
			ID: "claude-code.permissions", Strategy: releasecontract.StrategyJSONKeyMerge,
			Status: ConfigurationNotAssessed,
		},
		{
			ID: "credential-tools.secrets-store", Strategy: releasecontract.StrategySeedIfAbsent,
			Status: ConfigurationNotAssessed,
		},
	}
	if !reflect.DeepEqual(target.Configuration, wantResources) {
		t.Fatalf("configuration = %#v, want %#v", target.Configuration, wantResources)
	}
}

func TestPreviewRejectsInternalAndDuplicateSelections(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	tests := []struct {
		name       string
		components []domain.ComponentID
		message    string
	}{
		{
			name:       "internal component",
			components: []domain.ComponentID{domain.ComponentCodexGates},
			message:    "not selectable",
		},
		{
			name: "duplicate component",
			components: []domain.ComponentID{
				domain.ComponentCodex,
				domain.ComponentCodex,
			},
			message: "duplicate",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := service.Plan(test.components)
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("error = %v, want containing %q", err, test.message)
			}
		})
	}
}

func newTestService(t *testing.T, observed domain.ObservedState) Service {
	t.Helper()
	model := testModel(t)
	service, err := New(model, observed)
	if err != nil {
		t.Fatalf("service: %v", err)
	}
	return service
}

func testModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootClaudeConfig, "CLAUDE.md", "claude/CLAUDE.md"),
			},
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootCodexConfig, "AGENTS.md", "codex/AGENTS.md"),
			},
		},
		{
			ID: domain.ComponentOpenCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootOpenCodeConfig, "AGENTS.md", "opencode/AGENTS.md"),
			},
		},
		{ID: domain.ComponentCodexGates},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	return model
}

func desired(root domain.RootID, target, source domain.ArtifactPath) installmodel.ArtifactSpec {
	return installmodel.ArtifactSpec{
		Target:     domain.Location{Root: root, Path: target},
		SourcePath: source,
	}
}

func artifact(root domain.RootID, path domain.ArtifactPath, ownership domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{
		Location:  domain.Location{Root: root, Path: path},
		Ownership: ownership,
	}
}
