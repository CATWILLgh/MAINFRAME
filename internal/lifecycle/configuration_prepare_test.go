package lifecycle

import (
	"crypto/sha256"
	"fmt"
	"io/fs"
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareConfigurationRejectsUnsupportedGenericChangeBeforeMCP(t *testing.T) {
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
	if err == nil || len(prepared.Transitions()) != 0 {
		t.Fatalf("PrepareConfiguration() = %#v, %v; want rejection", prepared, err)
	}
}

func TestPrepareConfigurationIncludesCodexMCP(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleCodexProjection()},
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
	if len(transitions) != 1 || lifecycleMutationCount(transitions) != 2 ||
		transitions[0].ResourceIDs[0] != "codex.mcp.context7" {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
}

func TestPrepareConfigurationComposesOpenCodePermissionsAndMCP(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(
		[]releasecontract.Resource{lifecycleOpenCodePermissionResource()},
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
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || lifecycleMutationCount(transitions) != 3 ||
		len(transitions[0].ResourceIDs) != 2 ||
		transitions[0].ResourceIDs[0] != "opencode.mcp.context7" ||
		transitions[0].ResourceIDs[1] != "opencode.permissions" {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
	mutation := transitions[0].Mutations[0]
	if !mutation.After.Exists {
		t.Fatal("composed configuration has an absent after-image")
	}
	after := string(mutation.After.Content)
	if !strings.Contains(after, `"permission"`) ||
		!strings.Contains(after, `"context7"`) {
		t.Fatalf("composed configuration =\n%s", after)
	}
}

func TestPrepareConfigurationIncludesClaudeMCP(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleClaudeProjection()},
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
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		}},
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || lifecycleMutationCount(transitions) != 2 ||
		len(transitions[0].ResourceIDs) != 1 ||
		transitions[0].ResourceIDs[0] != "claude-code.mcp.context7" {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
	var foundConfig, foundRegistry bool
	for _, mutation := range transitions[0].Mutations {
		foundConfig = foundConfig || mutation.Target == (domain.Location{
			Root: domain.RootHome, Path: ".claude.json",
		})
		foundRegistry = foundRegistry || mutation.Target == (domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		})
	}
	if !foundConfig || !foundRegistry {
		t.Fatalf("Claude targets are incomplete: %#v", transitions)
	}
}

func TestPrepareConfigurationIncludesAntigravityMCP(t *testing.T) {
	host := lifecyclePreparationHost{}
	configurationInspection, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleAntigravityProjection()},
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
		Components: []domain.ComponentID{domain.ComponentAntigravity2},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentAntigravity2},
		}},
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || lifecycleMutationCount(transitions) != 2 ||
		len(transitions[0].ResourceIDs) != 1 ||
		transitions[0].ResourceIDs[0] != "antigravity-2.mcp.context7" {
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

func lifecycleOpenCodePermissionResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
		Strategy: releasecontract.StrategyJSONKeyMerge,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "opencode.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportSupported,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer: "/permission", DesiredMap: `{"bash":"deny"}`,
			RegistryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-permissions.json",
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

func (host lifecyclePreparationHost) InspectDigest(
	location domain.Location,
) (hostfs.Entry, error) {
	entry, err := host.Inspect(location, true)
	if err != nil {
		return hostfs.Entry{}, err
	}
	digest := sha256.Sum256(entry.Content)
	entry.SHA256 = fmt.Sprintf("%x", digest)
	entry.Content = nil
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

func lifecycleOpenCodeProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "opencode.mcp.context7", ComponentID: domain.ComponentOpenCode,
		Codec:    releasecontract.MCPProjectionOpenCodeRemote,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "opencode.json",
		},
		MapPointer: "/mcp", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json.mainframe-mcp.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"type":"remote","url":"https://mcp.context7.com/mcp"}`,
	}
}

func lifecycleClaudeProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "claude-code.mcp.context7", ComponentID: domain.ComponentClaudeCode,
		Codec:    releasecontract.MCPProjectionClaudeUserHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootHome, Path: ".claude.json",
		},
		MapPointer: "/mcpServers", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"type":"http","url":"https://mcp.context7.com/mcp"}`,
	}
}

func lifecycleAntigravityProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "antigravity-2.mcp.context7", ComponentID: domain.ComponentAntigravity2,
		Codec:    releasecontract.MCPProjectionAntigravityGlobalHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootAntigravityConfig, Path: "mcp_config.json",
		},
		MapPointer: "/mcpServers", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootAntigravityData, Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"serverUrl":"https://mcp.context7.com/mcp"}`,
	}
}
