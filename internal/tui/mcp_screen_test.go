package tui

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestEnvironmentSelectionOpensMCPOnboardingBeforePreview(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	updated, command := model.openMCP()
	if updated.screen != screenMCP {
		t.Fatalf("screen = %v", updated.screen)
	}
	for _, text := range []string{
		"Optional MCP integrations",
		"Context7",
		"Current, version-specific library documentation",
		"github.com/upstash/context7",
		"context7.com/docs/resources/all-clients",
		"github.com/upstash/context7#installation",
		"MIT",
		"Verified 2026-07-17",
	} {
		if !strings.Contains(updated.View().Content, text) {
			t.Fatalf("MCP view does not contain %q:\n%s", text, updated.View().Content)
		}
	}
	if command == nil {
		t.Fatal("opening the MCP screen must initialize its form")
	}
}

func TestMCPChoiceAppearsInReadOnlyPreview(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentCodex}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentCodex, domain.ComponentClaudeCode}

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
		"Configuration and credentials are not changed",
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

func TestMCPPreviewRejectsUnsupportedAdapterWithoutCallingLifecycle(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{domain.ComponentAntigravity2}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentAntigravity2}

	updated, command := model.openPreview()
	if updated.screen != screenMCP || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !strings.Contains(updated.View().Content, "plaintext-free secret reference") {
		t.Fatalf("compatibility error is missing:\n%s", updated.View().Content)
	}
	if previewer.calls != 0 {
		t.Fatalf("lifecycle preview calls = %d", previewer.calls)
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
	if updated.(*Model).screen != screenSelection || navigation == nil {
		t.Fatal("repository metadata prevented immediate back navigation")
	}
}
