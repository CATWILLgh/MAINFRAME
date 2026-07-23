package mcpconfiguration_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const antigravityDesired = `{"serverUrl":"https://mcp.context7.com/mcp"}`

func TestPrepareAntigravityAddPreservesUnrelatedConfiguration(t *testing.T) {
	config := []byte(
		`{"theme":"dark","mcpServers":{"docs":{"serverUrl":"https://docs.example/mcp"}},"telemetry":false}`,
	)
	inspection := inspectAntigravityPrepared(t, antigravityPreparedHost(config, nil))

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, antigravitySelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 2 ||
		len(transitions[0].ResourceIDs) != 1 ||
		transitions[0].ResourceIDs[0] != "antigravity-2.mcp.context7" {
		t.Fatalf("transitions = %#v", transitions)
	}
	configAfter := string(findPreparedAfter(t, transitions, antigravityConfigLocation()))
	for _, expected := range []string{
		`"theme": "dark"`, `"serverUrl": "https://mcp.context7.com/mcp"`,
		`"docs": {`, `"serverUrl": "https://docs.example/mcp"`, `"telemetry": false`,
	} {
		if !strings.Contains(configAfter, expected) {
			t.Fatalf("Antigravity config lacks %s:\n%s", expected, configAfter)
		}
	}
	if strings.Index(configAfter, `"docs"`) > strings.Index(configAfter, `"context7"`) {
		t.Fatalf("sibling MCP order changed:\n%s", configAfter)
	}
	registryAfter := string(findPreparedAfter(t, transitions, antigravityRegistryLocation()))
	if !strings.Contains(registryAfter, `"serverUrl": "https://mcp.context7.com/mcp"`) ||
		strings.Contains(registryAfter, `"url"`) || strings.Contains(registryAfter, `"type"`) {
		t.Fatalf("Antigravity registry dialect =\n%s", registryAfter)
	}
}

func TestPrepareAntigravityCreatesMissingFilesPrivately(t *testing.T) {
	inspection := inspectAntigravityPrepared(t, antigravityPreparedHost(nil, nil))
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, antigravitySelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	for _, mutation := range mutations {
		if mutation.Before.Exists || mutation.After.Mode != 0o600 {
			t.Fatalf("missing-file mutation = %#v", mutation)
		}
	}
}

func TestPrepareAntigravityReconcilesOwnedStates(t *testing.T) {
	old := `{"serverUrl":"https://old.example/mcp"}`
	tests := []struct {
		name       string
		config     string
		registry   string
		selections []mcpcatalog.Selection
		mutations  int
		configHas  string
		ownedHas   string
	}{
		{
			name: "update", config: `{"mcpServers":{"context7":` + old + `},"keep":true}`,
			registry: antigravityOwned(old), selections: antigravitySelection(), mutations: 2,
			configHas: `"serverUrl": "https://mcp.context7.com/mcp"`, ownedHas: `"context7": {`,
		},
		{
			name: "remove", config: `{"mcpServers":{"context7":` + antigravityDesired + `}}`,
			registry: antigravityOwned(antigravityDesired), mutations: 2,
			configHas: `"mcpServers": {}`, ownedHas: `"servers": {}`,
		},
		{
			name:     "relinquish",
			config:   `{"mcpServers":{"context7":{"serverUrl":"https://user.example/mcp"}}}`,
			registry: antigravityOwned(antigravityDesired), selections: antigravitySelection(),
			mutations: 1, ownedHas: `"context7": null`,
		},
		{
			name: "ready", config: `{"mcpServers":{"context7":` + antigravityDesired + `}}`,
			registry: antigravityOwned(antigravityDesired), selections: antigravitySelection(),
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			assertAntigravityPreparedState(t, test.config, test.registry, test.selections,
				test.mutations, test.configHas, test.ownedHas)
		})
	}
}

func assertAntigravityPreparedState(
	t *testing.T,
	config string,
	registry string,
	selections []mcpcatalog.Selection,
	wantMutations int,
	wantConfig string,
	wantOwned string,
) {
	t.Helper()
	inspection := inspectAntigravityPrepared(
		t, antigravityPreparedHost([]byte(config), []byte(registry)),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, selections,
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if wantMutations == 0 {
		if len(transitions) != 0 {
			t.Fatalf("ready transitions = %#v", transitions)
		}
		return
	}
	if len(transitions) != 1 || len(transitions[0].Mutations) != wantMutations {
		t.Fatalf("transitions = %#v", transitions)
	}
	if wantConfig != "" {
		after := string(findPreparedAfter(t, transitions, antigravityConfigLocation()))
		if !strings.Contains(after, wantConfig) {
			t.Fatalf("config after-image =\n%s", after)
		}
	}
	after := string(findPreparedAfter(t, transitions, antigravityRegistryLocation()))
	if !strings.Contains(after, wantOwned) {
		t.Fatalf("registry after-image =\n%s", after)
	}
}

func inspectAntigravityPrepared(
	t *testing.T,
	host *fakeHost,
) mcpconfiguration.Inspection {
	t.Helper()
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{antigravityProjection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	return inspection
}

func antigravityProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "antigravity-2.mcp.context7", ComponentID: domain.ComponentAntigravity2,
		Codec:    releasecontract.MCPProjectionAntigravityGlobalHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: antigravityConfigLocation(), MapPointer: "/mcpServers", EntryKey: "context7",
		RegistryTarget: antigravityRegistryLocation(), RegistrySchemaVersion: 1,
		RegistryEntriesPointer: "/servers", DesiredEntry: antigravityDesired,
	}
}

func antigravitySelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentAntigravity2},
	}}
}

func antigravityPreparedHost(config, registry []byte) *fakeHost {
	host := &fakeHost{entries: make(map[domain.Location]hostfs.Entry)}
	if config != nil {
		host.entries[antigravityConfigLocation()] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), config...),
			Mode: 0o644, Device: 11, Inode: 401,
		}
	}
	if registry != nil {
		host.entries[antigravityRegistryLocation()] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), registry...),
			Mode: 0o600, Device: 11, Inode: 402,
		}
	}
	return host
}

func antigravityConfigLocation() domain.Location {
	return domain.Location{Root: domain.RootAntigravityConfig, Path: "mcp_config.json"}
}

func antigravityRegistryLocation() domain.Location {
	return domain.Location{
		Root: domain.RootAntigravityData, Path: "mainframe/mcp-ownership.json",
	}
}

func antigravityOwned(value string) string {
	return `{"version":1,"servers":{"context7":` + value + `}}`
}
