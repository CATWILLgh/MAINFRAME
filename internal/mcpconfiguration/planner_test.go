package mcpconfiguration_test

import (
	"errors"
	"io/fs"
	"os"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const desired = `{"type":"remote","url":"https://mcp.context7.com/mcp"}`

func TestPlanReconcilesExactAdapterOwnedEntry(t *testing.T) {
	tests := []struct {
		name      string
		config    string
		registry  string
		selected  bool
		want      mcpconfiguration.IntentKind
		wantBlock bool
	}{
		{name: "add", config: `{}`, selected: true, want: mcpconfiguration.IntentAdd},
		{name: "unrelated wildcard does not conflict", config: `{"mcp":{"context*":` + desired + `}}`, selected: true, want: mcpconfiguration.IntentAdd},
		{name: "unowned exact conflicts", config: `{"mcp":{"context7":` + desired + `}}`, selected: true, want: mcpconfiguration.IntentConflict, wantBlock: true},
		{name: "ready ignores object order", config: `{"mcp":{"context7":{"url":"https://mcp.context7.com/mcp","type":"remote"}}}`, registry: owned(desired), selected: true, want: mcpconfiguration.IntentReady},
		{name: "update", config: `{"mcp":{"context7":{"type":"remote","url":"https://old.example/mcp"}}}`, registry: owned(`{"type":"remote","url":"https://old.example/mcp"}`), selected: true, want: mcpconfiguration.IntentUpdate},
		{name: "remove", config: `{"mcp":{"context7":` + desired + `}}`, registry: owned(desired), want: mcpconfiguration.IntentRemove},
		{name: "user change relinquishes", config: `{"mcp":{"context7":{"type":"remote","url":"https://user.example/mcp"}}}`, registry: owned(desired), selected: true, want: mcpconfiguration.IntentRelinquish},
		{name: "user deletion relinquishes", config: `{}`, registry: owned(desired), selected: true, want: mcpconfiguration.IntentRelinquish},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := &fakeHost{entries: entries(test.config, test.registry)}
			inspection, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{projection()}, catalog(t), host,
			)
			if err != nil {
				t.Fatalf("Inspect() error = %v", err)
			}
			selections := []mcpcatalog.Selection(nil)
			if test.selected {
				selections = []mcpcatalog.Selection{{
					ServerID: "context7", ProfileID: "remote-keyless",
					Adapters: []domain.ComponentID{domain.ComponentOpenCode},
				}}
			}
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentOpenCode}, selections,
			)
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			if len(plan.Intents) != 1 || plan.Intents[0].Kind != test.want || plan.Blocking != test.wantBlock {
				t.Fatalf("plan = %#v, want kind %q blocking %t", plan, test.want, test.wantBlock)
			}
			if host.reads != 2 {
				t.Fatalf("host reads = %d, want 2", host.reads)
			}
			_, _ = inspection.Plan([]domain.ComponentID{domain.ComponentOpenCode}, selections)
			if host.reads != 2 {
				t.Fatalf("planning reread host: %d", host.reads)
			}
		})
	}
}

func TestInspectRejectsUnvalidatedProjectionBeforeHostRead(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*releasecontract.MCPProjection)
	}{
		{name: "foreign root", mutate: func(item *releasecontract.MCPProjection) {
			item.Target.Root = domain.RootClaudeConfig
		}},
		{name: "unverified desired entry", mutate: func(item *releasecontract.MCPProjection) {
			item.DesiredEntry = `{"type":"remote","url":"https://example.test/mcp"}`
		}},
		{name: "invalid pointer", mutate: func(item *releasecontract.MCPProjection) {
			item.MapPointer = "/permission"
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			item := projection()
			test.mutate(&item)
			host := &fakeHost{}
			if _, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{item}, catalog(t), host,
			); err == nil {
				t.Fatal("unvalidated projection was accepted")
			}
			if host.reads != 0 {
				t.Fatalf("host was read %d times before projection validation", host.reads)
			}
		})
	}
}

func TestPlanKeepsUnsupportedAdapterDescriptiveAndRevalidatesSelection(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{}}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	selection := mcpcatalog.Selection{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentClaudeCode},
		[]mcpcatalog.Selection{selection},
	)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if len(plan.Intents) != 1 || plan.Intents[0].Kind != mcpconfiguration.IntentUnsupported {
		t.Fatalf("unsupported plan = %#v", plan)
	}
	selection.ProfileID = "unknown"
	if _, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentClaudeCode},
		[]mcpcatalog.Selection{selection},
	); err == nil {
		t.Fatal("untrusted profile selection was accepted")
	}
}

func TestPlanIgnoresUnmanagedSiblingAdapterConfigurationProblem(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		location("opencode.json"): {
			Kind: hostfs.EntryRegular, Content: []byte(`{"mcp":`),
		},
		location("opencode.json.mainframe-mcp.json"): {
			Kind: hostfs.EntryRegular, Content: []byte(`{"version":`),
		},
	}}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentClaudeCode},
		[]mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		}},
	)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if plan.Blocking || len(plan.Intents) != 1 ||
		plan.Intents[0].Kind != mcpconfiguration.IntentUnsupported {
		t.Fatalf("isolated adapter plan = %#v", plan)
	}
}

func TestRelinquishedOwnershipIgnoresUnsafeConfiguration(t *testing.T) {
	for _, selected := range []bool{false, true} {
		t.Run(map[bool]string{false: "deselected", true: "selected"}[selected], func(t *testing.T) {
			host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
				location("opencode.json"): {Kind: hostfs.EntrySymlink},
				location("opencode.json.mainframe-mcp.json"): {
					Kind:    hostfs.EntryRegular,
					Content: []byte(`{"version":1,"servers":{"context7":null}}`),
				},
			}}
			inspection, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{projection()}, catalog(t), host,
			)
			if err != nil {
				t.Fatal(err)
			}
			var selections []mcpcatalog.Selection
			if selected {
				selections = []mcpcatalog.Selection{{
					ServerID: "context7", ProfileID: "remote-keyless",
					Adapters: []domain.ComponentID{domain.ComponentOpenCode},
				}}
			}
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentOpenCode}, selections,
			)
			if err != nil {
				t.Fatal(err)
			}
			if selected {
				if plan.Blocking || len(plan.Intents) != 1 ||
					plan.Intents[0].Kind != mcpconfiguration.IntentRelinquish {
					t.Fatalf("selected tombstone plan = %#v", plan)
				}
			} else if plan.Blocking || len(plan.Intents) != 0 {
				t.Fatalf("deselected tombstone plan = %#v", plan)
			}
		})
	}
}

func TestPlanFailsClosedForMalformedStateWithoutPartialIntents(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		location("opencode.json"): {
			Kind: hostfs.EntryRegular, Content: []byte(`{"mcp":`),
		},
	}}
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentOpenCode},
		[]mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{
				domain.ComponentClaudeCode,
				domain.ComponentOpenCode,
			},
		}},
	)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if !plan.Blocking || len(plan.Intents) != 1 ||
		plan.Intents[0].Kind != mcpconfiguration.IntentConflict {
		t.Fatalf("malformed-state plan = %#v", plan)
	}
}

func TestPlanFailsClosedForUnsafeConfigurationState(t *testing.T) {
	tests := []struct {
		name     string
		entries  map[domain.Location]hostfs.Entry
		failures map[domain.Location]error
	}{
		{name: "configuration symlink", entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {Kind: hostfs.EntrySymlink},
		}},
		{name: "configuration directory", entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {Kind: hostfs.EntryDirectory},
		}},
		{name: "configuration read error", failures: map[domain.Location]error{
			location("opencode.json"): errors.New("unreadable"),
		}},
		{name: "registry invalid JSON", entries: entries(
			`{}`, `{"version":1,"servers":`,
		)},
		{name: "registry invalid schema", entries: entries(
			`{}`, `{"version":2,"servers":{}}`,
		)},
		{name: "registry symlink", entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"):                    {Kind: hostfs.EntryRegular, Content: []byte(`{}`)},
			location("opencode.json.mainframe-mcp.json"): {Kind: hostfs.EntrySymlink},
		}},
		{name: "registry read error", entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {Kind: hostfs.EntryRegular, Content: []byte(`{}`)},
		}, failures: map[domain.Location]error{
			location("opencode.json.mainframe-mcp.json"): errors.New("unreadable"),
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := &fakeHost{entries: test.entries, failures: test.failures}
			inspection, err := mcpconfiguration.Inspect(
				[]releasecontract.MCPProjection{projection()}, catalog(t), host,
			)
			if err != nil {
				t.Fatal(err)
			}
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentOpenCode},
				[]mcpcatalog.Selection{{
					ServerID: "context7", ProfileID: "remote-keyless",
					Adapters: []domain.ComponentID{domain.ComponentOpenCode},
				}},
			)
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			if !plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentConflict {
				t.Fatalf("unsafe-state plan = %#v", plan)
			}
		})
	}
}

func projection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "opencode.mcp.context7", ComponentID: domain.ComponentOpenCode,
		Codec:    releasecontract.MCPProjectionOpenCodeRemote,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: location("opencode.json"), MapPointer: "/mcp", EntryKey: "context7",
		RegistryTarget:        location("opencode.json.mainframe-mcp.json"),
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: desired,
	}
}

func catalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	result, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func entries(config, registry string) map[domain.Location]hostfs.Entry {
	result := make(map[domain.Location]hostfs.Entry)
	if config != "" {
		result[location("opencode.json")] = hostfs.Entry{Kind: hostfs.EntryRegular, Content: []byte(config)}
	}
	if registry != "" {
		result[location("opencode.json.mainframe-mcp.json")] = hostfs.Entry{Kind: hostfs.EntryRegular, Content: []byte(registry)}
	}
	return result
}

func owned(value string) string {
	return `{"version":1,"servers":{"context7":` + value + `}}`
}

func location(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootOpenCodeConfig, Path: path}
}

type fakeHost struct {
	entries  map[domain.Location]hostfs.Entry
	failures map[domain.Location]error
	reads    int
}

func (host *fakeHost) Inspect(location domain.Location, includeContent bool) (hostfs.Entry, error) {
	host.reads++
	if err := host.failures[location]; err != nil {
		return hostfs.Entry{}, err
	}
	entry, exists := host.entries[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	return entry, nil
}
