package lifecycle

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareConfigurationComposesGenericMCPAndDiagnostics(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(
		[]releasecontract.Resource{
			lifecycleOpenCodePermissionResource(),
			lifecycleDiagnosticsResource(domain.ComponentOpenCode),
		},
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleOpenCodeProjection()},
		lifecycleMCPCatalog(t),
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	service, err := NewWithInspections(
		testModel(t),
		domain.ObservedState{},
		configurationInspection,
		mcpInspection,
	)
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := service.PrepareConfiguration(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentOpenCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		}},
		Diagnostics: diagnostics.Desired{Configured: true, Feedback: true},
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}

	assertComposedDiagnosticsResources(t, prepared.Transitions())
}

func assertComposedDiagnosticsResources(
	t *testing.T,
	transitions []configuration.Transition,
) {
	t.Helper()
	resources := make(map[string]bool)
	var configured, diagnosticsConfigured bool
	for _, transition := range transitions {
		for _, resourceID := range transition.ResourceIDs {
			resources[resourceID] = true
		}
		for _, mutation := range transition.Mutations {
			content := string(mutation.After.Content)
			if mutation.Target.Path == "opencode.json" {
				configured = strings.Contains(content, `"permission"`) &&
					strings.Contains(content, `"context7"`)
			}
			if mutation.Target.Path == "mainframe/diagnostics.json" {
				diagnosticsConfigured = mutation.After.Exists &&
					strings.Contains(content, `"feedback": true`)
			}
		}
	}
	for _, resourceID := range []string{
		"opencode.permissions",
		"opencode.mcp.context7",
		"opencode.diagnostics",
	} {
		if !resources[resourceID] {
			t.Fatalf("missing resource %q in %#v", resourceID, transitions)
		}
	}
	if !configured || !diagnosticsConfigured {
		t.Fatalf("incomplete composed configuration: %#v", transitions)
	}
}
