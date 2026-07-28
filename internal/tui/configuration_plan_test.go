package tui

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

var configurationPlanFixture = lifecycle.Preview{
	Configuration: configuration.Plan{
		Changes: []configuration.Change{
			{
				ResourceID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
				UnitID: "bash", Kind: configuration.ChangeAdd,
			},
			{
				ResourceID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
				UnitID: "edit", Kind: configuration.ChangeUpdate,
			},
			{
				ResourceID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
				UnitID: "write", Kind: configuration.ChangeRemove,
			},
			{
				ResourceID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
				UnitID: "read", Kind: configuration.ChangeRelinquish,
			},
		},
		Issues: []configuration.Issue{
			{
				ResourceID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
				Kind:   configuration.IssuePlanningUnavailable,
				Reason: configuration.ObservationUnsupported,
			},
		},
		ManualActions: []configuration.ManualAction{
			{
				ResourceID: "codex.hook-trust", ComponentID: domain.ComponentCodex,
				Kind:   configuration.ManualActionCodexHookTrust,
				Reason: configuration.ManualActionRequired,
			},
		},
		Notices: []configuration.Notice{
			{
				ResourceID: "codex.hook-trust", ComponentID: domain.ComponentCodex,
				Reason: configuration.ExternalStateUnavailable,
			},
			{
				ResourceID:  "antigravity-2.live-activation",
				ComponentID: domain.ComponentAntigravity2,
				Reason:      configuration.ManualActionUnverified,
			},
		},
	},
}

func TestPreviewRendersConfigurationChangesAndIssues(t *testing.T) {
	previewer := &fakePreviewer{
		targets: []lifecycle.Target{
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusManaged, Selected: true},
		},
		preview: configurationPlanFixture,
	}
	model := newTestModel(t, previewer)
	updated, _ := model.openPreview()
	view := updated.View().Content

	for _, text := range []string{
		"Configuration plan",
		"Changes · 4",
		"add · OpenCode · opencode.permissions · bash · configuration + ownership registry",
		"update · OpenCode · opencode.permissions · edit · configuration + ownership registry",
		"remove · OpenCode · opencode.permissions · write · configuration + ownership registry",
		"stop managing · OpenCode · opencode.permissions · read · configuration + ownership registry",
		"Issues · 1",
		"planning unavailable · OpenCode · opencode.permissions · observation is not implemented",
		"Manual actions · 1",
		"Review MAINFRAME hooks in Codex with /hooks",
		"Notices · 2",
		"Codex is unavailable; hook trust was not inspected",
		"Antigravity 2.x activation remains manual and was not verified",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, view)
		}
	}
	if strings.Contains(view, "preserve user-owned") {
		t.Fatalf("relinquished deletion is described as preserved:\n%s", view)
	}
	if !reflect.DeepEqual(previewer.selected, []domain.ComponentID{domain.ComponentOpenCode}) {
		t.Fatalf("preview selection = %v", previewer.selected)
	}
}

func TestPreviewShowsDeselectedOpenCodeRemoval(t *testing.T) {
	previewer := &fakePreviewer{
		targets: []lifecycle.Target{
			{ID: domain.ComponentOpenCode, Status: lifecycle.StatusManaged, Selected: true},
		},
		preview: lifecycle.Preview{
			Configuration: configuration.Plan{
				Changes: []configuration.Change{
					{
						ResourceID:  "opencode.permissions",
						ComponentID: domain.ComponentOpenCode,
						UnitID:      "bash",
						Kind:        configuration.ChangeRemove,
					},
				},
			},
		},
	}
	model := newTestModel(t, previewer)
	model.selected = nil
	updated, _ := model.openPreview()

	if !strings.Contains(updated.View().Content, "remove · OpenCode · opencode.permissions · bash") {
		t.Fatalf("deselected removal is hidden:\n%s", updated.View().Content)
	}
}

func TestEmptyPreviewExplainsThatConfigurationNeedsNoChanges(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	updated, _ := model.openPreview()
	if !strings.Contains(updated.View().Content, "No configuration changes") {
		t.Fatalf("empty configuration preview is unexplained:\n%s", updated.View().Content)
	}
}
