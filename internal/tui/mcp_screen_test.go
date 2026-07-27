package tui

import (
	"errors"
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestEnvironmentSelectionOpensMCPListThenServerDetail(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	updated, command := model.openMCP()
	if updated.screen != screenMCP {
		t.Fatalf("screen = %v", updated.screen)
	}
	for _, text := range []string{
		"MCP integrations",
		"Context7",
		"Current, version-specific library documentation",
		"not configured",
		"Back to settings overview",
		"Nothing has been applied",
	} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("MCP view does not contain %q:\n%s", text, updated.View().Content)
		}
	}
	if strings.Contains(updated.View().Content, "Repository:") {
		t.Fatalf("MCP list expanded server details:\n%s", updated.View().Content)
	}
	if command == nil {
		t.Fatal("opening the MCP screen must initialize its form")
	}

	updated, command = updated.openMCPDetail("context7")
	if updated.screen != screenMCPDetail || command == nil {
		t.Fatalf("detail screen = %v, command = %v", updated.screen, command)
	}
	for _, text := range []string{
		"Configure Context7",
		"github.com/upstash/context7",
		"context7.com/docs/resources/all-clients",
		"github.com/upstash/context7#installation",
		"MIT",
		"Verified 2026-07-17",
		"Draft only — changes are applied with the complete plan",
	} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("MCP detail does not contain %q:\n%s", text, updated.View().Content)
		}
	}
}

func TestEmptyEnvironmentSelectionDisablesMCPAndReturnsToOverview(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := NewModel(previewer, testCatalog(t), nil, testCredentialState(t))
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openSelection()
	model.selected = nil
	if !strings.Contains(model.View().Content, "MCP integrations and additional DEV tools are unavailable") {
		t.Fatalf("empty selection does not explain MCP behavior:\n%s", model.View().Content)
	}

	updated, command := model.continueFromSelection()
	if command == nil || updated.screen != screenMain {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if previewer.calls != 0 || len(previewer.mcpSelections) != 0 || choice.Enabled {
		t.Fatalf(
			"preview calls = %d, selections = %#v, choice = %#v",
			previewer.calls, previewer.mcpSelections, choice,
		)
	}
}

func TestUnconfiguredMCPDefaultsFollowChangedEnvironmentSelection(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	if choice.Enabled || len(choice.Adapters) != 1 || choice.Adapters[0] != domain.ComponentClaudeCode {
		t.Fatalf("initial choice = %#v", choice)
	}

	model.selected = []domain.ComponentID{domain.ComponentCodex}
	model.openMCP()
	if choice.Enabled || len(choice.Adapters) != 1 || choice.Adapters[0] != domain.ComponentCodex {
		t.Fatalf("choice after environment change = %#v", choice)
	}
}

func TestMCPDetailBackReturnsToCatalogWithDraftStatus(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	model.openMCPDetail("context7")
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)
	if updated.screen != screenMCP || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	for _, text := range []string{"Context7", "Claude Code", "added to plan, not applied"} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("catalog does not contain %q:\n%s", text, updated.View().Content)
		}
	}
}

func TestMCPListEnterOpensFocusedIntegration(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()

	updatedModel, command := model.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEnter}))
	for attempt := 0; attempt < 3 && updatedModel.(*Model).screen == screenMCP && command != nil; attempt++ {
		updatedModel, command = updatedModel.Update(command())
	}
	updated := updatedModel.(*Model)
	if updated.screen != screenMCPDetail || updated.activeMCP != "context7" || command == nil {
		t.Fatalf(
			"screen = %v, active MCP = %q, command = %v",
			updated.screen, updated.activeMCP, command,
		)
	}
}

func TestMCPChoiceAppearsInReadOnlyPreview(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := NewModel(previewer, testCatalog(t), nil, testCredentialState(t))
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentCodex}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentCodex, domain.ComponentClaudeCode}
	choice.credentialInstanceID = "context7-home"

	updated, command := model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if len(previewer.mcpSelections) != 1 ||
		previewer.mcpSelections[0].ServerID != "context7" ||
		previewer.mcpSelections[0].ProfileID != "remote-api-key" {
		t.Fatalf("lifecycle MCP selections = %#v", previewer.mcpSelections)
	}
	for _, text := range []string{
		"MCP onboarding choices",
		"Context7",
		"Remote with API key",
		"Claude Code, Codex",
		"API key required",
		"Draft choice. Configuration changes only after complete-plan confirmation.",
	} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, updated.View().Content)
		}
	}
}

func TestMCPConfigurationIntentAppearsInPreview(t *testing.T) {
	previewer := &fakePreviewer{
		targets: defaultTargets(),
		preview: lifecycle.Preview{MCP: mcpconfiguration.Plan{
			Intents: []mcpconfiguration.Intent{{
				ComponentID: domain.ComponentClaudeCode,
				ServerID:    "context7",
				Kind:        mcpconfiguration.IntentAdd,
				Reason:      "selected entry is absent",
			}},
		}},
	}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-keyless"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}

	updated, command := model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	for _, text := range []string{
		"MCP configuration plan",
		"Claude Code · context7 · add",
		"selected entry is absent",
	} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("configuration preview does not contain %q:\n%s", text, updated.View().Content)
		}
	}
}

func TestMCPStatsIgnoreLateAndOffScreenResults(t *testing.T) {
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		fakeStatsSource{},
	)
	model.openMCP()
	staleGeneration := model.statsGeneration
	model.openMCP()
	currentGeneration := model.statsGeneration

	model.Update(repositoryStatsMsg{
		ServerID: "context7", Generation: staleGeneration,
		Stats: mcpcatalog.RepositoryStats{Stars: 11},
	})
	if strings.Contains(model.View().Content, "11 stars") {
		t.Fatal("late repository metadata was rendered")
	}
	model.Update(repositoryStatsMsg{
		ServerID: "context7", Generation: currentGeneration,
		Stats: mcpcatalog.RepositoryStats{Stars: 42},
	})
	if !strings.Contains(model.View().Content, "42 stars") {
		t.Fatalf("current stars are missing:\n%s", model.View().Content)
	}
	model.screen = screenPreview
	model.Update(repositoryStatsMsg{
		ServerID: "context7", Generation: currentGeneration,
		Stats: mcpcatalog.RepositoryStats{Stars: 99},
	})
	if model.repositoryStats["context7"].Stars != 42 {
		t.Fatal("off-screen repository metadata changed cached display state")
	}
}

func TestMCPStatsFailureDoesNotBlockNavigation(t *testing.T) {
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		fakeStatsSource{err: errors.New("rate limited")},
	)
	_, command := model.openMCP()
	if command == nil {
		t.Fatal("repository metadata must run as an asynchronous command")
	}
	updated, navigation := model.Update(keyPress("b"))
	if updated.(*Model).screen != screenMain || navigation == nil {
		t.Fatal("repository metadata prevented immediate back navigation")
	}
}
