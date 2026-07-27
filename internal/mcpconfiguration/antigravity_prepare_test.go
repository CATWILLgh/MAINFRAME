package mcpconfiguration_test

import (
	"crypto/sha256"
	"fmt"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const antigravityDesired = `{"serverUrl":"https://mcp.context7.com/mcp"}`
const antigravityFakeSecret = "fake-antigravity-context7-value"

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

func TestPrepareKeyedAntigravityDefersSecretAndStoresDigestOwnership(t *testing.T) {
	t.Setenv("CONTEXT7_HOME_KEY", antigravityFakeSecret)
	inspection := inspectAntigravityPrepared(
		t,
		antigravityPreparedHost(nil, nil),
	)
	bound, err := inspection.WithCredentialBindings([]mcpconfiguration.CredentialBinding{{
		ComponentID: domain.ComponentAntigravity2,
		ServerID:    "context7", ProfileID: "remote-api-key",
		EnvironmentVariable: "CONTEXT7_HOME_KEY",
	}})
	if err != nil {
		t.Fatalf("WithCredentialBindings() error = %v", err)
	}

	prepared, err := bound.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2},
		keyedAntigravitySelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	recipes := prepared.Materializations()
	if len(recipes) != 1 {
		t.Fatalf("materializations = %#v", recipes)
	}
	recipe := recipes[0]
	if recipe.ResourceID != "antigravity-2.mcp.context7" ||
		recipe.ConfigTarget != antigravityConfigLocation() ||
		recipe.ConfigEntryPointer != "/mcpServers/context7" ||
		recipe.ConfigValuePointer != "/mcpServers/context7/headers/CONTEXT7_API_KEY" ||
		recipe.RegistryTarget != antigravityRegistryLocation() ||
		recipe.RegistryDigestPointer != "/servers/context7/entry_sha256" ||
		recipe.SecretReference != "CONTEXT7_HOME_KEY" {
		t.Fatalf("materialization = %#v", recipe)
	}
	for _, transition := range prepared.Transitions() {
		for _, mutation := range transition.Mutations {
			content := string(mutation.After.Content)
			if strings.Contains(content, antigravityFakeSecret) {
				t.Fatalf("prepared content contains secret value: %s", content)
			}
		}
	}
	configAfter := string(findPreparedAfter(
		t,
		prepared.Transitions(),
		antigravityConfigLocation(),
	))
	if !strings.Contains(configAfter, configuration.DeferredSecretJSONPlaceholder) ||
		strings.Contains(configAfter, "CONTEXT7_HOME_KEY") {
		t.Fatalf("deferred config = %s", configAfter)
	}
	registryAfter := string(findPreparedAfter(
		t,
		prepared.Transitions(),
		antigravityRegistryLocation(),
	))
	for _, expected := range []string{
		`"format": "antigravity-literal-secret-v1"`,
		`"profile": "remote-api-key"`,
		`"secret_reference": "CONTEXT7_HOME_KEY"`,
		`"entry_sha256": "` + configuration.DeferredSecretDigestPlaceholder + `"`,
	} {
		if !strings.Contains(registryAfter, expected) {
			t.Fatalf("ownership registry lacks %s:\n%s", expected, registryAfter)
		}
	}
}

func TestKeyedAntigravityDigestOwnershipDetectsDrift(t *testing.T) {
	managed := `{"headers":{"CONTEXT7_API_KEY":"old-fake-value"},"serverUrl":"https://mcp.context7.com/mcp"}`
	registry := antigravitySecretOwned(managed, "CONTEXT7_HOME_KEY")
	tests := []struct {
		name        string
		configEntry string
		wantRecipe  bool
		wantNull    bool
	}{
		{name: "owned entry refreshes", configEntry: managed, wantRecipe: true},
		{
			name:        "user change relinquishes",
			configEntry: `{"serverUrl":"https://user.example/mcp"}`,
			wantNull:    true,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			config := `{"mcpServers":{"context7":` + test.configEntry + `}}`
			inspection := inspectAntigravityPrepared(
				t,
				antigravityPreparedHost([]byte(config), []byte(registry)),
			)
			bound, err := inspection.WithCredentialBindings(
				[]mcpconfiguration.CredentialBinding{{
					ComponentID: domain.ComponentAntigravity2,
					ServerID:    "context7", ProfileID: "remote-api-key",
					EnvironmentVariable: "CONTEXT7_HOME_KEY",
				}},
			)
			if err != nil {
				t.Fatal(err)
			}
			prepared, err := bound.Prepare(
				[]domain.ComponentID{domain.ComponentAntigravity2},
				keyedAntigravitySelection(),
			)
			if err != nil {
				t.Fatal(err)
			}
			if got := len(prepared.Materializations()) == 1; got != test.wantRecipe {
				t.Fatalf("has materialization = %v, want %v", got, test.wantRecipe)
			}
			if test.wantNull {
				after := string(findPreparedAfter(
					t,
					prepared.Transitions(),
					antigravityRegistryLocation(),
				))
				if !strings.Contains(after, `"context7": null`) {
					t.Fatalf("relinquished registry = %s", after)
				}
			}
		})
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

func keyedAntigravitySelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-api-key",
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

func antigravitySecretOwned(value string, reference string) string {
	digest := sha256.Sum256([]byte(value))
	return fmt.Sprintf(
		`{"version":1,"servers":{"context7":{"format":"antigravity-literal-secret-v1","profile":"remote-api-key","secret_backend":"environment","secret_reference":%q,"entry_sha256":"%x"}}}`,
		reference,
		digest,
	)
}
