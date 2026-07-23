package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
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
		{ID: domain.ComponentAntigravity2, Status: StatusAbsent},
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
		domain.ComponentAntigravity2,
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	wantKinds := map[domain.ComponentID]domain.OperationKind{
		domain.ComponentClaudeCode:   domain.OperationInstall,
		domain.ComponentCodex:        domain.OperationRemove,
		domain.ComponentOpenCode:     domain.OperationInstall,
		domain.ComponentAntigravity2: domain.OperationInstall,
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
			Reason:   ConfigurationObservationUnsupported,
		},
	}
	if !reflect.DeepEqual(target.Configuration, want) {
		t.Fatalf("configuration = %#v, want %#v", target.Configuration, want)
	}
}

func TestPreviewUsesValidatedConfigurationObservations(t *testing.T) {
	model := testModel(t)
	resources := []releasecontract.Resource{
		{
			ID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode,
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportUnimplemented,
		},
	}
	service, err := NewWithConfiguration(
		model,
		domain.ObservedState{},
		resources,
		[]configuration.Observation{
			{
				ResourceID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode,
				Status: configuration.NeedsChange, Reason: configuration.ResourceMissing,
			},
		},
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}
	want := []ConfigurationResource{
		{
			ID: "claude-code.credentials-index", Strategy: releasecontract.StrategySeedIfAbsent,
			Status: ConfigurationNeedsChange, Reason: ConfigurationResourceMissing,
		},
	}
	if got := service.Targets()[0].Configuration; !reflect.DeepEqual(got, want) {
		t.Fatalf("configuration = %#v, want %#v", got, want)
	}
}

func TestPreviewRejectsIncompleteOrInconsistentConfigurationObservations(t *testing.T) {
	model := testModel(t)
	resources := []releasecontract.Resource{
		{
			ID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode,
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportUnimplemented,
		},
	}
	tests := map[string][]configuration.Observation{
		"missing": {},
		"unknown": {
			{ResourceID: "unknown", ComponentID: domain.ComponentClaudeCode, Status: configuration.Ready, Reason: configuration.ResourceExists},
		},
		"component mismatch": {
			{ResourceID: "claude-code.credentials-index", ComponentID: domain.ComponentCodex, Status: configuration.Ready, Reason: configuration.ResourceExists},
		},
		"impossible status": {
			{ResourceID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode, Status: configuration.NotAssessed, Reason: configuration.ObservationUnsupported},
		},
		"duplicate": {
			{ResourceID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode, Status: configuration.Ready, Reason: configuration.ResourceExists},
			{ResourceID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode, Status: configuration.Ready, Reason: configuration.ResourceExists},
		},
	}
	for name, observations := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := NewWithConfiguration(model, domain.ObservedState{}, resources, observations); err == nil {
				t.Fatal("invalid configuration observations were accepted")
			}
		})
	}
}

func TestPreviewRequiresObservationsForSupportedConfiguration(t *testing.T) {
	_, err := NewWithResources(
		testModel(t),
		domain.ObservedState{},
		[]releasecontract.Resource{
			{
				ID: "claude-code.credentials-index", ComponentID: domain.ComponentClaudeCode,
				Strategy:    releasecontract.StrategySeedIfAbsent,
				Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportUnimplemented,
			},
		},
	)
	if err == nil || !strings.Contains(err.Error(), "requires an observation") {
		t.Fatalf("NewWithResources() error = %v", err)
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
		{ID: domain.ComponentAntigravity2},
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
				Strategy:    releasecontract.StrategyJSONKeyMerge,
				Target:      domain.Location{Root: domain.RootClaudeConfig, Path: "settings.json"},
				Observation: releasecontract.SupportUnimplemented, Apply: releasecontract.SupportUnimplemented,
			},
			{
				ID: "credential-tools.secrets-store", ComponentID: "credential-tools",
				Strategy:    releasecontract.StrategySeedIfAbsent,
				Target:      domain.Location{Root: domain.RootHome, Path: ".config/mainframe/secrets"},
				Observation: releasecontract.SupportUnimplemented, Apply: releasecontract.SupportUnimplemented,
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
			Status: ConfigurationNotAssessed, Reason: ConfigurationObservationUnsupported,
		},
		{
			ID: "credential-tools.secrets-store", Strategy: releasecontract.StrategySeedIfAbsent,
			Status: ConfigurationNotAssessed, Reason: ConfigurationObservationUnsupported,
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
				{
					UnitID: "claude-code.dev.harness-feedback",
					Target: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "skills/mainframe-dev",
					},
					SourcePath: "dev/harness-feedback-plugin",
					Feature:    domain.FeatureHarnessFeedback,
				},
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
		{
			ID: domain.ComponentAntigravity2,
			Artifacts: []installmodel.ArtifactSpec{
				desired(
					domain.RootAntigravityConfig,
					"plugins/mainframe",
					"antigravity-2/plugin",
				),
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
