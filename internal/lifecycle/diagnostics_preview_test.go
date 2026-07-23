package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestPreviewBuildsDiagnosticsPlan(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	result, err := service.Preview(PreviewRequest{
		Components: []domain.ComponentID{
			domain.ComponentOpenCode,
			domain.ComponentClaudeCode,
		},
		Diagnostics: diagnostics.Desired{Configured: true, Events: true},
	})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	want := diagnostics.Plan{Intents: []diagnostics.Intent{
		{ComponentID: domain.ComponentClaudeCode, Events: true},
		{ComponentID: domain.ComponentOpenCode, Events: true},
	}}
	if !reflect.DeepEqual(result.Diagnostics, want) {
		t.Fatalf("diagnostics = %#v, want %#v", result.Diagnostics, want)
	}
	if result.Diagnostics.Executable {
		t.Fatal("unscoped diagnostics preview became executable")
	}
}

func TestPreviewAddsContextToDiagnosticsErrors(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	_, err := service.Preview(PreviewRequest{
		Components:  []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{Events: true},
	})
	if err == nil || !strings.Contains(err.Error(), "plan diagnostics: diagnostics features require") {
		t.Fatalf("Preview() error = %v", err)
	}
}

func TestPreviewDerivesHarnessFeedbackInstallFeatureFromDEVChoice(t *testing.T) {
	model := feedbackFeatureModel(t)
	service, err := New(model, domain.ObservedState{})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	withoutFeedback, err := service.Preview(PreviewRequest{
		Components:  []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{Configured: true, Events: true},
	})
	if err != nil {
		t.Fatalf("Preview() without feedback error = %v", err)
	}
	if len(withoutFeedback.Filesystem.Operations) != 0 {
		t.Fatalf(
			"filesystem operations without feedback = %#v",
			withoutFeedback.Filesystem.Operations,
		)
	}

	withFeedback, err := service.Preview(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{
			Configured: true,
			Events:     true,
			Feedback:   true,
		},
	})
	if err != nil {
		t.Fatalf("Preview() with feedback error = %v", err)
	}
	if len(withFeedback.Filesystem.Operations) != 1 ||
		withFeedback.Filesystem.Operations[0].Kind != domain.OperationInstall {
		t.Fatalf(
			"filesystem operations with feedback = %#v",
			withFeedback.Filesystem.Operations,
		)
	}
}

func TestPreviewRemovesHarnessFeedbackWhenItIsDisabledInsideDEV(t *testing.T) {
	model := feedbackFeatureModel(t)
	service, err := New(model, domain.ObservedState{
		Components: []domain.ObservedComponent{{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{{
				Location: domain.Location{
					Root: domain.RootClaudeConfig,
					Path: "skills/mainframe-dev",
				},
				UnitID:    "claude-code.dev.harness-feedback",
				Ownership: domain.OwnershipManagedExact,
			}},
		}},
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	preview, err := service.Preview(PreviewRequest{
		Components:  []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{Configured: true, Events: true},
	})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.Filesystem.Operations) != 1 ||
		preview.Filesystem.Operations[0].Kind != domain.OperationRemove {
		t.Fatalf("filesystem operations = %#v", preview.Filesystem.Operations)
	}
}

func TestPreviewIgnoresDisabledFeatureUnitsInBaseTargetStatus(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				{
					UnitID: "claude-code.instructions",
					Target: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "CLAUDE.md",
					},
					SourcePath: "CLAUDE.md",
				},
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
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	service, err := New(
		model,
		domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{
				{
					Location: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "CLAUDE.md",
					},
					UnitID:    "claude-code.instructions",
					Ownership: domain.OwnershipManagedExact,
				},
				{
					Location: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "skills/mainframe-dev",
					},
					UnitID:    "claude-code.dev.harness-feedback",
					Ownership: domain.OwnershipManagedExact,
				},
			},
		}}},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	if status := service.Targets()[0].Status; status != StatusManaged {
		t.Fatalf("status = %q, want %q", status, StatusManaged)
	}
}

func feedbackFeatureModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
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
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	return model
}

func TestPrepareConfigurationRejectsUnscopedDiagnostics(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	prepared, err := service.PrepareConfiguration(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{
			Configured: true,
			Events:     true,
			Feedback:   true,
		},
	})
	if err == nil || !strings.Contains(err.Error(), "diagnostics resource") {
		t.Fatalf("PrepareConfiguration() = %#v, %v", prepared, err)
	}
}
