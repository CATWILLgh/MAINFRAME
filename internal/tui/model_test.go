package tui

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestSelectionViewSeparatesFilesystemAndConfigurationStatus(t *testing.T) {
	model := NewModel(&fakePreviewer{targets: []lifecycle.Target{
		{
			ID: domain.ComponentClaudeCode, Status: lifecycle.StatusManaged, Selected: true,
			Configuration: []lifecycle.ConfigurationResource{
				{
					ID:       "claude-code.permissions",
					Strategy: "json-key-merge",
					Status:   lifecycle.ConfigurationNotAssessed,
				},
			},
		},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAttention, Selected: true},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
	}})
	model.Init()

	view := model.View()
	for _, text := range []string{
		"READ-ONLY RELEASE PREVIEW",
		"Configuration resources are inventoried but not assessed or applied",
		"Claude Code — installed · configuration not assessed (1)",
		"Codex — needs attention",
		"OpenCode — not detected",
	} {
		if !strings.Contains(view.Content, text) {
			t.Fatalf("view does not contain %q:\n%s", text, view.Content)
		}
	}
	if !view.AltScreen {
		t.Fatal("selection view must use the alternate screen")
	}
	if !reflect.DeepEqual(model.selected, []domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentCodex,
	}) {
		t.Fatalf("selected = %v", model.selected)
	}
}

func TestPreviewViewGroupsObservableOperations(t *testing.T) {
	previewer := &fakePreviewer{
		targets: []lifecycle.Target{
			{
				ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent,
				Configuration: []lifecycle.ConfigurationResource{
					{
						ID:       "claude-code.permissions",
						Strategy: "json-key-merge",
						Status:   lifecycle.ConfigurationNotAssessed,
					},
				},
			},
			{ID: domain.ComponentCodex, Status: lifecycle.StatusManaged, Selected: true},
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		},
		plan: domain.Plan{Operations: []domain.Operation{
			operation(domain.ComponentClaudeCode, domain.OperationInstall, domain.RootClaudeConfig, "CLAUDE.md"),
			operation(domain.ComponentCodex, domain.OperationRemove, domain.RootCodexConfig, "AGENTS.md"),
			operation(domain.ComponentOpenCode, domain.OperationConflict, domain.RootOpenCodeConfig, "AGENTS.md"),
		}},
	}
	model := NewModel(previewer)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}

	updated, command := model.openPreview()
	if command != nil {
		t.Fatal("opening a synchronous preview returned a command")
	}
	view := updated.View().Content
	for _, text := range []string{
		"Filesystem plan",
		"Install · 1",
		"Remove · 1",
		"Conflicts · 1",
		"Claude Code",
		"Codex",
		"OpenCode",
		"Configuration inventory · 1",
		"claude-code.permissions · json-key-merge · not assessed",
		"b back",
		"q quit",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, view)
		}
	}
	if !reflect.DeepEqual(previewer.selected, model.selected) {
		t.Fatalf("preview selection = %v, want %v", previewer.selected, model.selected)
	}
}

func TestSelectedConfigurationDeduplicatesSharedDependencyResources(t *testing.T) {
	shared := lifecycle.ConfigurationResource{
		ID: "credential-tools.secrets-store", Strategy: "seed-if-absent",
		Status: lifecycle.ConfigurationNotAssessed,
	}
	targets := []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Configuration: []lifecycle.ConfigurationResource{shared}},
		{ID: domain.ComponentCodex, Configuration: []lifecycle.ConfigurationResource{shared}},
	}
	got := selectedConfiguration(targets, []domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentCodex,
	})
	if !reflect.DeepEqual(got, []lifecycle.ConfigurationResource{shared}) {
		t.Fatalf("configuration = %#v, want one shared resource", got)
	}
}

func TestHuhSelectionUpdatesModelOwnedDesiredState(t *testing.T) {
	model := NewModel(&fakePreviewer{targets: defaultTargets()})
	model.Init()
	updated, _ := model.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeySpace, Text: " "}))
	model = updated.(*Model)

	want := []domain.ComponentID{domain.ComponentClaudeCode}
	if !reflect.DeepEqual(model.selected, want) {
		t.Fatalf("selected = %v, want %v", model.selected, want)
	}
}

func TestPreviewBackPreservesSelection(t *testing.T) {
	model := NewModel(&fakePreviewer{targets: []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
	}})
	model.selected = []domain.ComponentID{domain.ComponentOpenCode}
	model.screen = screenPreview

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)
	if updated.screen != screenSelection {
		t.Fatalf("screen = %v", updated.screen)
	}
	if !reflect.DeepEqual(updated.selected, model.selected) {
		t.Fatalf("selected = %v, want %v", updated.selected, model.selected)
	}
	if command == nil {
		t.Fatal("returning to the form must initialize it")
	}
}

func TestEmptyPreviewExplainsThatFilesystemNeedsNoChanges(t *testing.T) {
	model := NewModel(&fakePreviewer{targets: defaultTargets()})
	updated, _ := model.openPreview()
	if !strings.Contains(updated.View().Content, "No filesystem changes") {
		t.Fatalf("empty preview is unexplained:\n%s", updated.View().Content)
	}
}

func TestPreviewErrorIsRenderedWithoutLeavingSelection(t *testing.T) {
	model := NewModel(&fakePreviewer{
		targets: []lifecycle.Target{
			{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
			{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		},
		err: errors.New("planner unavailable"),
	})

	updated, command := model.openPreview()
	if updated.screen != screenSelection {
		t.Fatalf("screen = %v", updated.screen)
	}
	if !strings.Contains(updated.View().Content, "planner unavailable") {
		t.Fatalf("error not rendered:\n%s", updated.View().Content)
	}
	if command == nil {
		t.Fatal("selection form was not reinitialized after a preview error")
	}
}

func TestQuitKeysReturnAQuitCommand(t *testing.T) {
	for _, key := range []string{"q", "ctrl+c"} {
		model := NewModel(&fakePreviewer{targets: defaultTargets()})
		_, command := model.Update(keyPress(key))
		if command == nil {
			t.Fatalf("key %q did not return a quit command", key)
		}
	}
}

func TestEscapeAbortsSelectionButReturnsFromPreview(t *testing.T) {
	selection := NewModel(&fakePreviewer{targets: defaultTargets()})
	selection.Init()
	_, command := selection.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEscape}))
	if command == nil {
		t.Fatal("escape did not abort selection")
	}

	preview := NewModel(&fakePreviewer{targets: defaultTargets()})
	preview.screen = screenPreview
	updated, command := preview.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEscape}))
	if updated.(*Model).screen != screenSelection || command == nil {
		t.Fatal("escape did not return from preview to selection")
	}
}

type fakePreviewer struct {
	targets  []lifecycle.Target
	plan     domain.Plan
	err      error
	selected []domain.ComponentID
}

func (fake *fakePreviewer) Targets() []lifecycle.Target {
	return append([]lifecycle.Target(nil), fake.targets...)
}

func (fake *fakePreviewer) Plan(selected []domain.ComponentID) (domain.Plan, error) {
	fake.selected = append([]domain.ComponentID(nil), selected...)
	return fake.plan, fake.err
}

func defaultTargets() []lifecycle.Target {
	return []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
	}
}

func operation(
	component domain.ComponentID,
	kind domain.OperationKind,
	root domain.RootID,
	path domain.ArtifactPath,
) domain.Operation {
	return domain.Operation{
		ComponentID: component,
		Kind:        kind,
		Artifact: domain.Artifact{
			Location: domain.Location{Root: root, Path: path},
		},
	}
}

func keyPress(value string) tea.KeyPressMsg {
	if value == "ctrl+c" {
		return tea.KeyPressMsg(tea.Key{Code: 'c', Mod: tea.ModCtrl})
	}
	return tea.KeyPressMsg(tea.Key{Code: rune(value[0]), Text: value})
}
