package lifecycle

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareConfigurationRejectsUnsupportedMCPSelection(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(nil, host)
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
		testModel(t), domain.ObservedState{}, configurationInspection, mcpInspection,
	)
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := service.PrepareConfiguration(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		}},
	})
	if err == nil || len(prepared.Transitions()) != 0 {
		t.Fatalf("PrepareConfiguration() = %#v, %v; want rejection", prepared, err)
	}
}
