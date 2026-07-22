package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
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

func TestPrepareConfigurationRejectsConfiguredDiagnostics(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	prepared, err := service.PrepareConfiguration(PreviewRequest{
		Components:  []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{Configured: true, Feedback: true},
	})
	if err == nil || err.Error() !=
		"configured diagnostics are not executable and cannot be prepared" {
		t.Fatalf("PrepareConfiguration() = %#v, %v", prepared, err)
	}
}
