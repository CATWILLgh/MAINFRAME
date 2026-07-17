package lifecycle

import (
	"io/fs"
	"os"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareConfigurationComposesCodexMCPAfterImages(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(
		[]releasecontract.Resource{lifecycleGenericResource()},
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	catalog := lifecycleMCPCatalog(t)
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleCodexProjection()},
		catalog,
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
		Components: []domain.ComponentID{domain.ComponentCodex},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentCodex},
		}},
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 2 || lifecycleMutationCount(transitions) != 4 ||
		transitions[0].ResourceIDs[0] != "codex.mcp.context7" ||
		transitions[1].ResourceIDs[0] != "codex.generic" {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
}

func lifecycleGenericResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "codex.generic", ComponentID: domain.ComponentCodex,
		Strategy: releasecontract.StrategyJSONKeyMerge,
		Target: domain.Location{
			Root: domain.RootCodexConfig, Path: "generic.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer: "/permission", DesiredMap: `{"bash":"deny"}`,
			RegistryTarget: domain.Location{
				Root: domain.RootCodexConfig, Path: "mainframe/generic-ownership.json",
			},
			RegistrySchemaVersion: 1, EntriesPointer: "/actions",
			EntrySchema: "decision-rule-v1",
		},
	}
}

func lifecycleMutationCount(transitions []configuration.Transition) int {
	total := 0
	for _, transition := range transitions {
		total += len(transition.Mutations)
	}
	return total
}

type lifecyclePreparationHost map[domain.Location]hostfs.Entry

func (host lifecyclePreparationHost) Inspect(
	location domain.Location,
	_ bool,
) (hostfs.Entry, error) {
	entry, exists := host[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	return entry, nil
}

func lifecycleMCPCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatal(err)
	}
	return catalog
}

func lifecycleCodexProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "codex.mcp.context7", ComponentID: domain.ComponentCodex,
		Codec:    releasecontract.MCPProjectionCodexUserHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootCodexConfig, Path: "config.toml",
		},
		MapPointer: "/mcp_servers", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootCodexConfig, Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion:  1,
		RegistryEntriesPointer: "/servers",
		DesiredEntry:           `{"url":"https://mcp.context7.com/mcp"}`,
	}
}
