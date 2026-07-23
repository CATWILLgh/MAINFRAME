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

func TestAdditionalScreenMakesHarnessFeedbackSubordinateToDEV(t *testing.T) {
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
		"Additional",
		"Enable DEV mode",
		"Nothing is sent over the network",
		"Each environment keeps its own MAINFRAME data",
		"Harness feedback becomes available inside DEV mode",
		"Draft only",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("diagnostics view does not contain %q:\n%s", text, view)
		}
	}
	if strings.Contains(view, "Enable harness feedback") {
		t.Fatalf("feedback question is visible before DEV is enabled:\n%s", view)
	}
	updatedModel, command := model.Update(keyPress("left"))
	updated = updatedModel.(*Model)
	for attempt := 0; attempt < 3 && command != nil; attempt++ {
		updatedModel, command = updatedModel.Update(command())
	}
	updatedModel, command = updatedModel.Update(keyPress("enter"))
	updated = updatedModel.(*Model)
	for attempt := 0; attempt < 3 && command != nil; attempt++ {
		updatedModel, command = updatedModel.Update(command())
	}
	updated = updatedModel.(*Model)
	if view = updated.View().Content; !strings.Contains(view, "Enable harness feedback") {
		t.Fatalf("feedback question is hidden after DEV is enabled:\n%s", view)
	}
}

func TestAdditionalChoicesMapDEVAndFeedbackToOneDraft(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openDiagnostics()
	model.diagnosticsDEVEnabled = true
	model.diagnosticsFeedbackEnabled = true

	updated, command := model.continueFromDiagnostics()

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !updated.diagnostics.Events || !updated.diagnostics.Feedback {
		t.Fatalf("diagnostics draft = %#v", updated.diagnostics)
	}
}

func TestDisablingDEVAlsoDisablesHarnessFeedback(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.diagnostics = diagnostics.Desired{
		Configured: true,
		Events:     true,
		Feedback:   true,
	}
	model.openDiagnostics()
	model.diagnosticsDEVEnabled = false

	updated, _ := model.continueFromDiagnostics()

	if !updated.diagnostics.Configured || updated.diagnostics.Events ||
		updated.diagnostics.Feedback {
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
		"DEV tools draft",
		"DEV event history — disable for Claude Code, OpenCode",
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
	model.diagnosticsDEVEnabled = true

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !updated.diagnostics.Configured || !updated.diagnostics.Events {
		t.Fatalf("diagnostics draft = %#v", updated.diagnostics)
	}
}
