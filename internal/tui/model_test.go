package tui

import (
	"context"
	"errors"
	"os"
	"reflect"
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestSelectionViewSeparatesFilesystemAndConfigurationStatus(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{
		{
			ID: domain.ComponentClaudeCode, Status: lifecycle.StatusManaged, Selected: true,
			Configuration: []lifecycle.ConfigurationResource{
				{
					ID:       "claude-code.permissions",
					Strategy: "json-key-merge",
					Status:   lifecycle.ConfigurationNotAssessed,
					Reason:   lifecycle.ConfigurationObservationUnsupported,
				},
			},
		},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAttention, Selected: true},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentAntigravity2, Status: lifecycle.StatusAbsent},
	}})
	model.openSelection()

	view := model.View()
	for _, text := range []string{
		"PLAN BEFORE APPLY",
		"Configure your choices first",
		"Nothing changes until you review and confirm the complete plan",
		"This build is preview-only; Apply remains disabled",
		"Return to the overview to configure MCP and additional DEV tools",
		"Claude Code — installed · configuration 1 not assessed",
		"Codex — needs attention",
		"OpenCode — not detected",
		"Antigravity 2.x — not detected",
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
						Reason:   lifecycle.ConfigurationObservationUnsupported,
					},
				},
			},
			{ID: domain.ComponentCodex, Status: lifecycle.StatusManaged, Selected: true},
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		},
		preview: lifecycle.Preview{
			Filesystem: domain.Plan{Operations: []domain.Operation{
				operation(domain.ComponentClaudeCode, domain.OperationInstall, domain.RootClaudeConfig, "CLAUDE.md"),
				operation(domain.ComponentCodex, domain.OperationAdopt, domain.RootCodexConfig, "rules/mainframe.rules"),
				operation(domain.ComponentCodex, domain.OperationReplace, domain.RootCodexConfig, "skills"),
				operation(domain.ComponentCodex, domain.OperationRemove, domain.RootCodexConfig, "AGENTS.md"),
				operation(domain.ComponentOpenCode, domain.OperationRelinquish, domain.RootOpenCodeConfig, "commands"),
				operation(domain.ComponentOpenCode, domain.OperationConflict, domain.RootOpenCodeConfig, "AGENTS.md"),
			}},
		},
	}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}

	updated, command := model.openPreview()
	if command != nil {
		t.Fatal("opening a synchronous preview returned a command")
	}
	view := updated.View().Content
	assertViewContains(t, view, []string{
		"Filesystem plan",
		"Install · 1",
		"Adopt existing · 1",
		"Update · 1",
		"Remove · 1",
		"Stop managing · 1",
		"Conflicts · 1",
		"Claude Code",
		"Codex",
		"OpenCode",
		"Configuration plan",
		"No configuration changes",
		"b back",
		"q quit",
	})
	if !reflect.DeepEqual(previewer.selected, model.selected) {
		t.Fatalf("preview selection = %v, want %v", previewer.selected, model.selected)
	}
	if updated.reviewedPlan == nil {
		t.Fatal("successful review did not retain the opaque reviewed plan")
	}
}

func assertViewContains(t *testing.T, view string, expected []string) {
	t.Helper()
	for _, text := range expected {
		if !strings.Contains(view, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, view)
		}
	}
}

func TestConfigurationStatusSummarizesOnlyActionableAndUnknownStates(t *testing.T) {
	resources := []lifecycle.ConfigurationResource{
		{ID: "ready", Status: lifecycle.ConfigurationReady},
		{ID: "change-a", Status: lifecycle.ConfigurationNeedsChange},
		{ID: "change-b", Status: lifecycle.ConfigurationNeedsChange},
		{ID: "attention", Status: lifecycle.ConfigurationAttention},
		{ID: "unknown", Status: lifecycle.ConfigurationNotAssessed},
		{ID: "optional", Status: lifecycle.ConfigurationNotApplicable},
		{
			ID: "manual", Status: lifecycle.ConfigurationNeedsChange,
			Reason: lifecycle.ConfigurationManualActionRequired,
		},
	}
	if got := configurationStatus(resources); got !=
		" · configuration 2 changes, 1 warning, 1 not assessed, 1 manual action" {
		t.Fatalf("status = %q", got)
	}
}

func TestConfigurationLabelsExplainEveryObservationReason(t *testing.T) {
	reasons := map[lifecycle.ConfigurationReason]string{
		lifecycle.ConfigurationResourceExists:           "file exists",
		lifecycle.ConfigurationDirectoryExists:          "directory exists",
		lifecycle.ConfigurationLinePresent:              "line is present",
		lifecycle.ConfigurationResourceMissing:          "file is missing",
		lifecycle.ConfigurationDirectoryMissing:         "directory is missing",
		lifecycle.ConfigurationLineMissing:              "line is missing",
		lifecycle.ConfigurationOptionalTargetMissing:    "optional file is absent",
		lifecycle.ConfigurationSymbolicLink:             "symbolic link is not followed",
		lifecycle.ConfigurationWrongKind:                "unexpected file type",
		lifecycle.ConfigurationInspectionFailed:         "inspection failed",
		lifecycle.ConfigurationObservationUnsupported:   "observation is not implemented",
		lifecycle.ConfigurationJSONFieldsMatch:          "owned fields match",
		lifecycle.ConfigurationJSONFieldsDrifted:        "owned fields differ",
		lifecycle.ConfigurationJSONDocumentInvalid:      "JSON document is invalid",
		lifecycle.ConfigurationExternalStateSatisfied:   "external state is ready",
		lifecycle.ConfigurationManualActionRequired:     "manual action is required",
		lifecycle.ConfigurationExternalStateUnavailable: "external state is unavailable",
		lifecycle.ConfigurationExternalInspectionFailed: "external inspection failed",
	}
	for reason, want := range reasons {
		if got := configurationReasonName(reason); got != want {
			t.Fatalf("reason %q = %q, want %q", reason, got, want)
		}
	}
	statuses := map[lifecycle.ConfigurationStatus]string{
		lifecycle.ConfigurationReady:         "ready",
		lifecycle.ConfigurationNeedsChange:   "needs change",
		lifecycle.ConfigurationNotApplicable: "not applicable",
		lifecycle.ConfigurationAttention:     "needs attention",
		lifecycle.ConfigurationNotAssessed:   "not assessed",
	}
	for status, want := range statuses {
		if got := configurationStatusName(status); got != want {
			t.Fatalf("status %q = %q, want %q", status, got, want)
		}
	}
}

func TestHuhSelectionUpdatesModelOwnedDesiredState(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.openSelection()
	updated, _ := model.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeySpace, Text: " "}))
	model = updated.(*Model)

	want := []domain.ComponentID{domain.ComponentClaudeCode}
	if !reflect.DeepEqual(model.selected, want) {
		t.Fatalf("selected = %v, want %v", model.selected, want)
	}
}

func TestPreviewBackPreservesSelection(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
	}})
	model.selected = []domain.ComponentID{domain.ComponentOpenCode}
	model.screen = screenPreview
	model.reviewedPlan = fakeReviewedPlan{}

	updatedModel, command := model.Update(keyPress("b"))
	updated := updatedModel.(*Model)
	if updated.screen != screenMain {
		t.Fatalf("screen = %v", updated.screen)
	}
	if !reflect.DeepEqual(updated.selected, model.selected) {
		t.Fatalf("selected = %v, want %v", updated.selected, model.selected)
	}
	if command == nil {
		t.Fatal("returning to the form must initialize it")
	}
	if updated.reviewedPlan != nil {
		t.Fatal("returning from preview retained an executable reviewed plan")
	}
}

func TestEmptyPreviewExplainsThatFilesystemNeedsNoChanges(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	updated, _ := model.openPreview()
	if !strings.Contains(updated.View().Content, "No filesystem changes") {
		t.Fatalf("empty preview is unexplained:\n%s", updated.View().Content)
	}
}

func TestPreviewErrorIsRenderedWithoutLeavingSelection(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{
		targets: []lifecycle.Target{
			{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
			{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		},
		err: errors.New("planner unavailable"),
	})
	model.reviewedPlan = fakeReviewedPlan{}
	model.preview = lifecycle.Preview{Diagnostics: diagnostics.Plan{Executable: true}}
	model.mcpPreview = mcpcatalog.OnboardingPreview{
		Connections: []mcpcatalog.Connection{{}},
	}

	updated, command := model.openPreview()
	if updated.screen != screenMain {
		t.Fatalf("screen = %v", updated.screen)
	}
	if !strings.Contains(updated.View().Content, "planner unavailable") {
		t.Fatalf("error not rendered:\n%s", updated.View().Content)
	}
	if command == nil {
		t.Fatal("selection form was not reinitialized after a preview error")
	}
	if updated.reviewedPlan != nil ||
		updated.preview.Diagnostics.Executable ||
		len(updated.mcpPreview.Connections) != 0 {
		t.Fatal("failed review retained stale plan state")
	}
}

func TestQuitKeysReturnAQuitCommand(t *testing.T) {
	for _, key := range []string{"q", "ctrl+c"} {
		model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
		model.screen = screenPreview
		model.reviewedPlan = fakeReviewedPlan{}
		model.preview = lifecycle.Preview{
			Diagnostics: diagnostics.Plan{Executable: true},
		}
		model.mcpPreview = mcpcatalog.OnboardingPreview{
			Connections: []mcpcatalog.Connection{{}},
		}
		updatedModel, command := model.Update(keyPress(key))
		if command == nil {
			t.Fatalf("key %q did not return a quit command", key)
		}
		updated := updatedModel.(*Model)
		if updated.reviewedPlan != nil ||
			updated.preview.Diagnostics.Executable ||
			len(updated.mcpPreview.Connections) != 0 {
			t.Fatalf("key %q retained reviewed plan state", key)
		}
	}
}

func TestEscapeAbortsSelectionAndReturnsFromPreviewToRelevantStep(t *testing.T) {
	selection := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	selection.openSelection()
	_, command := selection.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEscape}))
	if command == nil {
		t.Fatal("escape did not abort selection")
	}

	preview := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	preview.screen = screenPreview
	updated, command := preview.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEscape}))
	if updated.(*Model).screen != screenMain || command == nil {
		t.Fatal("empty selection did not return from preview to settings overview")
	}

	preview.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	preview.screen = screenPreview
	updated, command = preview.Update(tea.KeyPressMsg(tea.Key{Code: tea.KeyEscape}))
	if updated.(*Model).screen != screenMain || command == nil {
		t.Fatal("selected environment did not return from preview to settings overview")
	}
}

type fakePreviewer struct {
	targets       []lifecycle.Target
	preview       lifecycle.Preview
	err           error
	selected      []domain.ComponentID
	mcpSelections []mcpcatalog.Selection
	diagnostics   diagnostics.Desired
	calls         int
}

func (fake *fakePreviewer) Targets() []lifecycle.Target {
	return append([]lifecycle.Target(nil), fake.targets...)
}

func (fake *fakePreviewer) Review(request application.Request) (ReviewedPlan, error) {
	fake.calls++
	fake.selected = append([]domain.ComponentID(nil), request.Components...)
	fake.mcpSelections = append([]mcpcatalog.Selection(nil), request.MCPSelections...)
	fake.diagnostics = request.Diagnostics
	if fake.err != nil {
		return nil, fake.err
	}
	return fakeReviewedPlan{semantic: fake.preview}, nil
}

type fakeReviewedPlan struct {
	semantic lifecycle.Preview
}

func (plan fakeReviewedPlan) Semantic() lifecycle.Preview {
	return plan.semantic
}

type fakeStatsSource struct {
	stats mcpcatalog.RepositoryStats
	err   error
}

func (fake fakeStatsSource) Stats(
	context.Context,
	mcpcatalog.Repository,
) (mcpcatalog.RepositoryStats, error) {
	return fake.stats, fake.err
}

func newTestModel(t *testing.T, reviewer PlanReviewer) *Model {
	return NewModel(reviewer, testCatalog(t), nil)
}

func testCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	return catalog
}

func defaultTargets() []lifecycle.Target {
	return []lifecycle.Target{
		{ID: domain.ComponentClaudeCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentCodex, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentOpenCode, Status: lifecycle.StatusAbsent},
		{ID: domain.ComponentAntigravity2, Status: lifecycle.StatusAbsent},
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
