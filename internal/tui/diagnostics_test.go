package tui

import (
	"reflect"
	"strings"
	"testing"

	"charm.land/lipgloss/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestDiagnosticsScreenReusesLocalDEVCapabilitiesAsSeparateChoices(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentCodex,
	}

	updated, command := model.openDiagnostics()

	if updated.screen != screenDiagnostics || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	view := updated.View().Content
	for _, text := range []string{
		"Local diagnostics",
		"Choose what to keep locally",
		"Diagnostic event history",
		"Harness feedback reports",
		"Nothing is sent over the network",
		"Each environment keeps its own MAINFRAME data",
		"Draft only",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("diagnostics view does not contain %q:\n%s", text, view)
		}
	}
}

func TestDiagnosticsFeaturesMapToIndependentDraftChoices(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openDiagnostics()
	model.diagnosticsSelected = []diagnosticsFeature{
		diagnosticsEvents,
		diagnosticsFeedback,
	}

	updated, command := model.continueFromDiagnostics()

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !updated.diagnostics.Events || !updated.diagnostics.Feedback {
		t.Fatalf("diagnostics draft = %#v", updated.diagnostics)
	}
}

func TestDiagnosticsNoticesFitANarrowTerminal(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openDiagnostics()

	for _, line := range strings.Split(model.View().Content, "\n") {
		if (strings.Contains(line, "network") || strings.Contains(line, "Draft only")) &&
			lipgloss.Width(line) > 72 {
			t.Fatalf("diagnostics notice is %d columns wide: %q", lipgloss.Width(line), line)
		}
	}
	if height := lipgloss.Height(model.View().Content); height > 24 {
		t.Fatalf("diagnostics screen is %d lines tall, want at most 24", height)
	}
}

func TestDiagnosticsDraftExplainsActivationRemovalAndRetainedHistory(t *testing.T) {
	desired := diagnostics.Desired{Configured: true, Events: true, Feedback: true}
	previewer := &fakePreviewer{
		targets: defaultTargets(),
		preview: lifecycle.Preview{Diagnostics: diagnostics.Plan{Intents: []diagnostics.Intent{
			{ComponentID: domain.ComponentClaudeCode},
			{ComponentID: domain.ComponentOpenCode},
		}}},
	}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentOpenCode,
	}
	model.diagnostics = desired

	updated, command := model.openPreview()

	if updated.screen != screenPreview || command != nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	view := updated.View().Content
	for _, text := range []string{
		"Local diagnostics draft",
		"Local event history — disable for Claude Code, OpenCode",
		"Harness feedback — disable for Claude Code, OpenCode",
		"ensure the activation configuration is absent",
		"Stored diagnostic history stays",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, view)
		}
	}
	if previewer.calls != 1 {
		t.Fatalf("preview calls = %d", previewer.calls)
	}
	if !reflect.DeepEqual(previewer.diagnostics, desired) {
		t.Fatalf("diagnostics request = %#v, want %#v", previewer.diagnostics, desired)
	}
}

func TestBackingOutOfDiagnosticsSavesItsDraft(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openDiagnostics()
	model.diagnosticsSelected = []diagnosticsFeature{diagnosticsEvents}

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !updated.diagnostics.Configured || !updated.diagnostics.Events {
		t.Fatalf("diagnostics draft = %#v", updated.diagnostics)
	}
}
