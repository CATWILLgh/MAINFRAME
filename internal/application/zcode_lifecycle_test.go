package application

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestZCodeLifecycleApplicabilityAcceptsOnlyLocalAdapterScope(t *testing.T) {
	request := Request{Components: []domain.ComponentID{domain.ComponentZCodeDesktop}}
	operation := domain.Operation{
		ComponentID: domain.ComponentZCodeDesktop,
		UnitID:      "zcode-desktop.instructions",
		Kind:        domain.OperationInstall,
	}
	semantic := lifecycle.Preview{Filesystem: domain.Plan{Operations: []domain.Operation{operation}}}
	preview := executor.Preview{Plan: semantic.Filesystem}
	if !zcodeLifecycleApplicable(request, semantic, preview) {
		t.Fatal("exact local ZCode lifecycle was inapplicable")
	}

	request.MCPSelections = []mcpcatalog.Selection{{ServerID: "context7"}}
	if zcodeLifecycleApplicable(request, semantic, preview) {
		t.Fatal("ZCode lifecycle admitted MCP authority")
	}
	request.MCPSelections = nil
	request.Diagnostics = diagnostics.Desired{Configured: true, Events: true}
	if zcodeLifecycleApplicable(request, semantic, preview) {
		t.Fatal("ZCode lifecycle admitted diagnostics authority")
	}
}

func TestZCodeLifecycleApplicabilityRejectsForeignOperationsAndTargets(t *testing.T) {
	request := Request{Components: []domain.ComponentID{domain.ComponentZCodeDesktop}}
	semantic := lifecycle.Preview{Filesystem: domain.Plan{Operations: []domain.Operation{{
		ComponentID: domain.ComponentOpenCode,
		UnitID:      "foreign",
		Kind:        domain.OperationInstall,
	}}}}
	if zcodeLifecycleApplicable(request, semantic, executor.Preview{Plan: semantic.Filesystem}) {
		t.Fatal("ZCode lifecycle admitted a foreign component operation")
	}

	transition := configuration.Transition{
		ResourceIDs: []string{"zcode-desktop.hooks"},
		Mutations: []configuration.FileMutation{{Target: domain.Location{
			Root: domain.RootZCodeConfig, Path: "foreign.json",
		}}},
	}
	if zcodeLifecycleTransition(transition, "", false) {
		t.Fatal("ZCode lifecycle admitted a foreign configuration target")
	}
}
