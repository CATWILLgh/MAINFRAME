package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestMainMenuIsTheFirstScreenAndExplainsCombinedApply(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusManaged, Selected: true},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
	}})
	model.Init()

	if model.screen != screenMain {
		t.Fatalf("screen = %v", model.screen)
	}
	view := model.View().Content
	for _, text := range []string{
		"Settings overview",
		"Environments — 1 selected",
		"MCP integrations — not configured",
		"Local diagnostics — not configured",
		"Review complete plan",
		"Nothing changes until you review and confirm the complete plan",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("main menu does not contain %q:\n%s", text, view)
		}
	}
}

func TestMainMenuRequiresAnEnvironmentForMCPAndDiagnostics(t *testing.T) {
	for _, choice := range []mainMenuChoice{mainMenuMCP, mainMenuDiagnostics} {
		model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
		model.mainMenuChoice = choice

		updated, command := model.continueFromMain()

		if updated.screen != screenMain || command == nil {
			t.Fatalf("choice %q: screen = %v, command = %v", choice, updated.screen, command)
		}
		if !strings.Contains(updated.View().Content, "Select at least one environment first") {
			t.Fatalf("choice %q has no explanation:\n%s", choice, updated.View().Content)
		}
	}
}

func TestEnvironmentSelectionReturnsToMainAndClearsDependentDraftsWhenEmpty(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.diagnostics = diagnosticsChoice{Configured: true, Events: true, Feedback: true}
	model.ensureMCPChoices()
	model.mcpChoices["context7"].Enabled = true
	model.mcpChoices["context7"].Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	model.selected = nil

	updated, command := model.continueFromSelection()

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if updated.diagnostics != (diagnosticsChoice{}) {
		t.Fatalf("diagnostics draft = %#v", updated.diagnostics)
	}
	if updated.mcpChoices["context7"].Enabled {
		t.Fatalf("MCP draft was not cleared: %#v", updated.mcpChoices["context7"])
	}
}

func TestBackingOutOfEnvironmentSelectionStillReconcilesDependentDrafts(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.diagnostics = diagnosticsChoice{Configured: true, Events: true}
	model.ensureMCPChoices()
	model.mcpChoices["context7"].Enabled = true
	model.mcpChoices["context7"].Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openSelection()
	model.selected = nil

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)

	if updated.screen != screenMain || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if updated.diagnostics != (diagnosticsChoice{}) || updated.mcpChoices["context7"].Enabled {
		t.Fatalf("dependent drafts remain: diagnostics=%#v MCP=%#v", updated.diagnostics, updated.mcpChoices["context7"])
	}
}
