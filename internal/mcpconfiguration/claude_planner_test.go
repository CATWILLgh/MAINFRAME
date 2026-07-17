package mcpconfiguration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const claudeDesired = `{"type":"http","url":"https://mcp.context7.com/mcp"}`

func TestPlanReconcilesExactClaudeOwnedEntry(t *testing.T) {
	tests := []struct {
		name      string
		config    string
		registry  string
		selected  bool
		want      mcpconfiguration.IntentKind
		wantBlock bool
	}{
		{name: "add", config: `{}`, selected: true, want: mcpconfiguration.IntentAdd},
		{name: "unowned exact conflicts", config: `{"mcpServers":{"context7":` + claudeDesired + `}}`, selected: true, want: mcpconfiguration.IntentConflict, wantBlock: true},
		{name: "ready", config: `{"mcpServers":{"context7":{"url":"https://mcp.context7.com/mcp","type":"http"}},"userID":"preserved"}`, registry: claudeOwned(claudeDesired), selected: true, want: mcpconfiguration.IntentReady},
		{name: "update", config: `{"mcpServers":{"context7":{"type":"http","url":"https://old.example/mcp"}}}`, registry: claudeOwned(`{"type":"http","url":"https://old.example/mcp"}`), selected: true, want: mcpconfiguration.IntentUpdate},
		{name: "remove", config: `{"mcpServers":{"context7":` + claudeDesired + `}}`, registry: claudeOwned(claudeDesired), want: mcpconfiguration.IntentRemove},
		{name: "user change relinquishes", config: `{"mcpServers":{"context7":{"type":"http","url":"https://user.example/mcp"}}}`, registry: claudeOwned(claudeDesired), selected: true, want: mcpconfiguration.IntentRelinquish},
		{name: "user deletion relinquishes", config: `{"mcpServers":{}}`, registry: claudeOwned(claudeDesired), selected: true, want: mcpconfiguration.IntentRelinquish},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := &fakeHost{entries: claudeEntries(test.config, test.registry)}
			inspection, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{claudeProjection()}, catalog(t), host,
			)
			if err != nil {
				t.Fatal(err)
			}
			var selections []mcpcatalog.Selection
			if test.selected {
				selections = []mcpcatalog.Selection{{
					ServerID: "context7", ProfileID: "remote-keyless",
					Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
				}}
			}
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentClaudeCode}, selections,
			)
			if err != nil {
				t.Fatal(err)
			}
			if len(plan.Intents) != 1 || plan.Intents[0].Kind != test.want ||
				plan.Blocking != test.wantBlock {
				t.Fatalf("plan = %#v", plan)
			}
		})
	}
}

func TestInspectRejectsUnsafeClaudeProjectionBeforeHostRead(t *testing.T) {
	tests := map[string]func(*releasecontract.MCPProjection){
		"foreign home path": func(item *releasecontract.MCPProjection) {
			item.Target.Path = ".profile"
		},
		"foreign registry": func(item *releasecontract.MCPProjection) {
			item.RegistryTarget = domain.Location{Root: domain.RootHome, Path: ".registry.json"}
		},
		"OpenCode dialect": func(item *releasecontract.MCPProjection) {
			item.DesiredEntry = `{"type":"remote","url":"https://mcp.context7.com/mcp"}`
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			projection := claudeProjection()
			mutate(&projection)
			host := &fakeHost{}
			if _, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{projection}, catalog(t), host,
			); err == nil {
				t.Fatal("unsafe projection was accepted")
			}
			if host.reads != 0 {
				t.Fatalf("host reads = %d, want 0", host.reads)
			}
		})
	}
}

func TestPlanKeepsSiblingIntentVisibleWhenClaudeStateBlocks(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		claudeLocation(".claude.json"): {
			Kind: hostfs.EntryRegular, Content: []byte(`{"mcpServers":`),
		},
		location("opencode.json"): {
			Kind: hostfs.EntryRegular, Content: []byte(`{}`),
		},
	}}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{claudeProjection(), projection()},
		catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentOpenCode},
		[]mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{
				domain.ComponentClaudeCode, domain.ComponentOpenCode,
			},
		}},
	)
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Blocking || len(plan.Intents) != 2 ||
		plan.Intents[0].ComponentID != domain.ComponentClaudeCode ||
		plan.Intents[0].Kind != mcpconfiguration.IntentConflict ||
		plan.Intents[1].ComponentID != domain.ComponentOpenCode ||
		plan.Intents[1].Kind != mcpconfiguration.IntentAdd {
		t.Fatalf("combined plan = %#v", plan)
	}
}

func claudeProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "claude-code.mcp.context7", ComponentID: domain.ComponentClaudeCode,
		Codec:    releasecontract.MCPProjectionClaudeUserHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: claudeLocation(".claude.json"), MapPointer: "/mcpServers",
		EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: claudeDesired,
	}
}

func claudeEntries(config, registry string) map[domain.Location]hostfs.Entry {
	result := make(map[domain.Location]hostfs.Entry)
	if config != "" {
		result[claudeLocation(".claude.json")] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: []byte(config),
		}
	}
	if registry != "" {
		result[domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		}] = hostfs.Entry{Kind: hostfs.EntryRegular, Content: []byte(registry)}
	}
	return result
}

func claudeOwned(value string) string {
	return `{"version":1,"servers":{"context7":` + value + `}}`
}

func claudeLocation(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootHome, Path: path}
}
