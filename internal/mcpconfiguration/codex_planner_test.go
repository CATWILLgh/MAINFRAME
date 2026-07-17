package mcpconfiguration_test

import (
	"errors"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const codexDesired = `{"url":"https://mcp.context7.com/mcp"}`

func TestPlanReconcilesExactCodexTOMLEntry(t *testing.T) {
	tests := []struct {
		name      string
		config    string
		registry  string
		selected  bool
		want      mcpconfiguration.IntentKind
		wantBlock bool
	}{
		{name: "add missing file", selected: true, want: mcpconfiguration.IntentAdd},
		{name: "add to empty document", config: "\n", selected: true, want: mcpconfiguration.IntentAdd},
		{
			name: "unowned exact conflicts", config: codexTOML("https://mcp.context7.com/mcp"),
			selected: true, want: mcpconfiguration.IntentConflict, wantBlock: true,
		},
		{
			name: "ready", config: codexTOML("https://mcp.context7.com/mcp"),
			registry: codexOwned(codexDesired), selected: true, want: mcpconfiguration.IntentReady,
		},
		{
			name: "update", config: codexTOML("https://old.example/mcp"),
			registry: codexOwned(`{"url":"https://old.example/mcp"}`),
			selected: true, want: mcpconfiguration.IntentUpdate,
		},
		{
			name: "remove", config: codexTOML("https://mcp.context7.com/mcp"),
			registry: codexOwned(codexDesired), want: mcpconfiguration.IntentRemove,
		},
		{
			name: "user change relinquishes", config: codexTOML("https://user.example/mcp"),
			registry: codexOwned(codexDesired), selected: true,
			want: mcpconfiguration.IntentRelinquish,
		},
		{
			name: "user deletion relinquishes", config: "[mcp_servers]\n",
			registry: codexOwned(codexDesired), selected: true,
			want: mcpconfiguration.IntentRelinquish,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			plan, host := planCodex(t, test.config, test.registry, test.selected, nil)
			if len(plan.Intents) != 1 || plan.Intents[0].Kind != test.want ||
				plan.Blocking != test.wantBlock {
				t.Fatalf("plan = %#v, want kind %q blocking %t", plan, test.want, test.wantBlock)
			}
			if host.reads != 2 {
				t.Fatalf("host reads = %d, want 2", host.reads)
			}
		})
	}
}

func TestCodexTOMLNonJSONValuesCannotMasqueradeAsManagedJSON(t *testing.T) {
	tests := map[string]string{
		"date":            "seen = 2026-07-17\n",
		"quoted date":     "seen = \"2026-07-17\"\n",
		"positive inf":    "weight = inf\n",
		"not a number":    "weight = nan\n",
		"array of tables": "[[mcp_servers.context7.rules]]\nname = \"one\"\n",
	}
	for name, extra := range tests {
		t.Run(name, func(t *testing.T) {
			config := codexTOML("https://mcp.context7.com/mcp") + extra
			plan, _ := planCodex(t, config, codexOwned(codexDesired), true, nil)
			if plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentRelinquish {
				t.Fatalf("plan = %#v", plan)
			}
		})
	}
}

func TestCodexTOMLLargeIntegerChangesAreComparedExactly(t *testing.T) {
	config := codexTOML("https://mcp.context7.com/mcp") + "revision = 9007199254740993\n"
	registry := codexOwned(`{"revision":9007199254740992,"url":"https://mcp.context7.com/mcp"}`)
	plan, _ := planCodex(t, config, registry, true, nil)
	if plan.Blocking || len(plan.Intents) != 1 ||
		plan.Intents[0].Kind != mcpconfiguration.IntentRelinquish {
		t.Fatalf("plan = %#v", plan)
	}
}

func TestCodexTOMLAcceptsQuotedKeysAndFailsClosedOnInvalidState(t *testing.T) {
	valid := "[mcp_servers.\"context7\"]\nurl = \"https://mcp.context7.com/mcp\"\n"
	plan, _ := planCodex(t, valid, "", true, nil)
	if !plan.Blocking || len(plan.Intents) != 1 ||
		plan.Intents[0].Reason != "existing entry is user owned" {
		t.Fatalf("quoted-key plan = %#v", plan)
	}

	invalid := map[string]string{
		"duplicate key":   "[mcp_servers.context7]\nurl = \"one\"\nurl = \"two\"\n",
		"redefined table": "mcp_servers = {}\n[mcp_servers.context7]\nurl = \"x\"\n",
		"wrong map type":  "mcp_servers = []\n",
	}
	for name, config := range invalid {
		t.Run(name, func(t *testing.T) {
			plan, _ := planCodex(t, config, "", true, nil)
			if !plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentConflict ||
				plan.Intents[0].Reason == "existing entry is user owned" {
				t.Fatalf("invalid-state plan = %#v", plan)
			}
		})
	}
}

func TestCodexInspectionRejectsUnsafeStateAndCodecBeforeRead(t *testing.T) {
	projection := codexProjection()
	projection.Target.Path = "settings.toml"
	host := &fakeHost{}
	if _, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection}, catalog(t), host,
	); err == nil || host.reads != 0 {
		t.Fatalf("unsafe projection error = %v, reads = %d", err, host.reads)
	}

	tests := []struct {
		name    string
		entry   hostfs.Entry
		failure error
	}{
		{name: "symlink", entry: hostfs.Entry{Kind: hostfs.EntrySymlink}},
		{name: "directory", entry: hostfs.Entry{Kind: hostfs.EntryDirectory}},
		{name: "read error", failure: errors.New("unreadable")},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			entries := map[domain.Location]hostfs.Entry{}
			failures := map[domain.Location]error{}
			if test.failure != nil {
				failures[codexLocation("config.toml")] = test.failure
			} else {
				entries[codexLocation("config.toml")] = test.entry
			}
			plan, _ := planCodex(t, "", "", true, &fakeHost{entries: entries, failures: failures})
			if !plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentConflict {
				t.Fatalf("unsafe-state plan = %#v", plan)
			}
		})
	}
}

func TestCodexAndOpenCodePlansRemainVisibleAndIsolated(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		codexLocation("config.toml"): {
			Kind: hostfs.EntryRegular, Content: []byte("[mcp_servers.context7\n"),
		},
		location("opencode.json"): {Kind: hostfs.EntryRegular, Content: []byte(`{}`)},
	}}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{codexProjection(), projection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentCodex, domain.ComponentOpenCode},
		[]mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentCodex, domain.ComponentOpenCode},
		}},
	)
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Blocking || len(plan.Intents) != 2 ||
		plan.Intents[0].ComponentID != domain.ComponentCodex ||
		plan.Intents[0].Kind != mcpconfiguration.IntentConflict ||
		plan.Intents[1].ComponentID != domain.ComponentOpenCode ||
		plan.Intents[1].Kind != mcpconfiguration.IntentAdd {
		t.Fatalf("combined plan = %#v", plan)
	}
}

func planCodex(
	t *testing.T,
	config string,
	registry string,
	selected bool,
	host *fakeHost,
) (mcpconfiguration.Plan, *fakeHost) {
	t.Helper()
	if host == nil {
		host = &fakeHost{entries: codexEntries(config, registry)}
	}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{codexProjection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	var selections []mcpcatalog.Selection
	if selected {
		selections = []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentCodex},
		}}
	}
	plan, err := inspection.Plan([]domain.ComponentID{domain.ComponentCodex}, selections)
	if err != nil {
		t.Fatal(err)
	}
	return plan, host
}

func codexProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "codex.mcp.context7", ComponentID: domain.ComponentCodex,
		Codec:    releasecontract.MCPProjectionCodec("codex-user-http-v1"),
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: codexLocation("config.toml"), MapPointer: "/mcp_servers",
		EntryKey:              "context7",
		RegistryTarget:        codexLocation("mainframe/mcp-ownership.json"),
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: codexDesired,
	}
}

func codexEntries(config, registry string) map[domain.Location]hostfs.Entry {
	result := make(map[domain.Location]hostfs.Entry)
	if config != "" {
		result[codexLocation("config.toml")] = hostfs.Entry{Kind: hostfs.EntryRegular, Content: []byte(config)}
	}
	if registry != "" {
		result[codexLocation("mainframe/mcp-ownership.json")] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: []byte(registry),
		}
	}
	return result
}

func codexTOML(endpoint string) string {
	return "[mcp_servers.context7]\nurl = \"" + endpoint + "\"\n"
}

func codexOwned(value string) string {
	return `{"version":1,"servers":{"context7":` + value + `}}`
}

func codexLocation(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootCodexConfig, Path: path}
}
