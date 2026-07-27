package tui

import (
	"context"
	"os"
	"testing"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type fakePreviewer struct {
	targets        []lifecycle.Target
	preview        lifecycle.Preview
	err            error
	selected       []domain.ComponentID
	mcpSelections  []mcpcatalog.Selection
	mcpCredentials []application.MCPCredentialBinding
	diagnostics    diagnostics.Desired
	calls          int
}

func (fake *fakePreviewer) Targets() []lifecycle.Target {
	return append([]lifecycle.Target(nil), fake.targets...)
}

func (fake *fakePreviewer) Review(request application.Request) (ReviewedPlan, error) {
	fake.calls++
	fake.selected = append([]domain.ComponentID(nil), request.Components...)
	fake.mcpSelections = append([]mcpcatalog.Selection(nil), request.MCPSelections...)
	fake.mcpCredentials = append(
		[]application.MCPCredentialBinding(nil),
		request.MCPCredentials...,
	)
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
