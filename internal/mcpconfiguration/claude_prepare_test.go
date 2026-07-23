package mcpconfiguration_test

import (
	"crypto/sha256"
	"encoding/hex"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareClaudeAddPreservesOrderedUserPreferences(t *testing.T) {
	config := []byte(`{"userID":"user","projects":{"/work":{"allowedTools":[]}},"mcpServers":{},"theme":"dark"}`)
	inspection := inspectClaudePrepared(t, claudePreparedHost(config, nil))

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, claudeSelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 ||
		!reflect.DeepEqual(transitions[0].ResourceIDs, []string{"claude-code.mcp.context7"}) {
		t.Fatalf("transitions = %#v", transitions)
	}
	configMutation := claudeMutationAt(t, transitions[0], claudeLocation(".claude.json"))
	want := strings.Join([]string{
		"{",
		`  "userID": "user",`,
		`  "projects": {`,
		`    "/work": {`,
		`      "allowedTools": []`,
		"    }",
		"  },",
		`  "mcpServers": {`,
		`    "context7": {`,
		`      "type": "http",`,
		`      "url": "https://mcp.context7.com/mcp"`,
		"    }",
		"  },",
		`  "theme": "dark"`,
		"}",
		"",
	}, "\n")
	assertClaudeMutation(t, configMutation, config, 0o644, 201, want)
	registry := claudeMutationAt(
		t,
		transitions[0],
		domain.Location{Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json"},
	)
	if !strings.Contains(string(registry.After.Content), `"type": "http"`) ||
		strings.Contains(string(registry.After.Content), `"type": "remote"`) {
		t.Fatalf("Claude registry after-image =\n%s", registry.After.Content)
	}
}

func TestPrepareClaudeCreatesMissingFilesPrivately(t *testing.T) {
	inspection := inspectClaudePrepared(t, claudePreparedHost(nil, nil))
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, claudeSelection(),
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

type claudeStateCase struct {
	name       string
	config     string
	registry   string
	selections []mcpcatalog.Selection
	wantCount  int
	wantConfig string
	wantOwned  string
}

func TestPrepareClaudeReconcilesOwnedStates(t *testing.T) {
	old := `{"type":"http","url":"https://old.example/mcp"}`
	tests := []claudeStateCase{
		{
			name: "update", config: `{"mcpServers":{"context7":` + old + `},"keep":true}`,
			registry: claudeOwned(old), selections: claudeSelection(), wantCount: 2,
			wantConfig: `"url": "https://mcp.context7.com/mcp"`, wantOwned: `"context7": {`,
		},
		{
			name: "remove", config: `{"mcpServers":{"context7":` + claudeDesired + `},"keep":true}`,
			registry: claudeOwned(claudeDesired), wantCount: 2,
			wantConfig: `"mcpServers": {}`, wantOwned: `"servers": {}`,
		},
		{
			name: "relinquish", config: `{"mcpServers":{"context7":{"type":"http","url":"https://user.example/mcp"}}}`,
			registry: claudeOwned(claudeDesired), selections: claudeSelection(), wantCount: 1,
			wantOwned: `"context7": null`,
		},
		{
			name: "ready", config: `{"mcpServers":{"context7":` + claudeDesired + `}}`,
			registry: claudeOwned(claudeDesired), selections: claudeSelection(), wantCount: 0,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			assertClaudePreparedState(t, test)
		})
	}
}

func assertClaudePreparedState(t *testing.T, test claudeStateCase) {
	t.Helper()
	inspection := inspectClaudePrepared(
		t, claudePreparedHost([]byte(test.config), []byte(test.registry)),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, test.selections,
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if test.wantCount == 0 {
		if len(transitions) != 0 {
			t.Fatalf("ready transitions = %#v", transitions)
		}
		return
	}
	if len(transitions) != 1 || len(transitions[0].Mutations) != test.wantCount {
		t.Fatalf("transitions = %#v", transitions)
	}
	if test.wantConfig != "" {
		config := claudeMutationAt(t, transitions[0], claudeLocation(".claude.json"))
		if !strings.Contains(string(config.After.Content), test.wantConfig) {
			t.Fatalf("config after-image =\n%s", config.After.Content)
		}
	}
	registry := claudeMutationAt(
		t,
		transitions[0],
		domain.Location{Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json"},
	)
	if !strings.Contains(string(registry.After.Content), test.wantOwned) {
		t.Fatalf("registry after-image =\n%s", registry.After.Content)
	}
}

func TestPrepareClaudeOntoComposesFutureSharedTarget(t *testing.T) {
	config := []byte(`{"preferences":{"theme":"light"},"mcpServers":{},"userID":"kept"}`)
	host := claudePreparedHost(config, nil)
	inspection := inspectClaudePrepared(t, host)
	digest := sha256.Sum256(config)
	base, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{"claude-code.preferences"},
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      claudeLocation(".claude.json"),
			Before: configuration.BeforeImage{
				Exists: true, SHA256: hex.EncodeToString(digest[:]),
				Mode: 0o644, Device: 9, Inode: 201,
			},
			After: configuration.AfterImage{
				Exists: true,
				Content: []byte(
					`{"preferences":{"theme":"dark"},"mcpServers":{},"userID":"kept"}`,
				),
				Mode: 0o600,
			},
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := inspection.PrepareOnto(
		base,
		[]domain.ComponentID{domain.ComponentClaudeCode},
		claudeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 2 ||
		!reflect.DeepEqual(
			transitions[0].ResourceIDs,
			[]string{"claude-code.mcp.context7", "claude-code.preferences"},
		) {
		t.Fatalf("composed transitions = %#v", transitions)
	}
	after := string(claudeMutationAt(
		t, transitions[0], claudeLocation(".claude.json"),
	).After.Content)
	for _, expected := range []string{`"theme": "dark"`, `"context7": {`, `"userID": "kept"`} {
		if !strings.Contains(after, expected) {
			t.Fatalf("composed config lacks %s:\n%s", expected, after)
		}
	}
}

func TestPrepareClaudeComposesMultipleServers(t *testing.T) {
	second := claudeProjection()
	second.ID = "claude-code.mcp.docs"
	second.ServerID = "docs"
	second.EntryKey = "docs"
	second.DesiredEntry = `{"type":"http","url":"https://docs.example/mcp"}`
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{claudeProjection(), second},
		twoServerCatalog(t),
		claudePreparedHost(nil, nil),
	)
	if err != nil {
		t.Fatal(err)
	}
	selections := []mcpcatalog.Selection{
		{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		},
		{
			ServerID: "docs", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		},
	}

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, selections,
	)
	if err != nil {
		t.Fatal(err)
	}
	transition := prepared.Transitions()[0]
	config := claudeMutationAt(t, transition, claudeLocation(".claude.json"))
	registry := claudeMutationAt(
		t,
		transition,
		domain.Location{Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json"},
	)
	for _, expected := range []string{`"context7": {`, `"docs": {`} {
		if !strings.Contains(string(config.After.Content), expected) ||
			!strings.Contains(string(registry.After.Content), expected) {
			t.Fatalf("multiple-server after-images lack %s: %#v", expected, transition)
		}
	}
}

func TestPrepareKeepsClaudeAndOpenCodeDialectsIsolated(t *testing.T) {
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{claudeProjection(), projection()},
		catalog(t),
		&fakeHost{entries: map[domain.Location]hostfs.Entry{}},
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentOpenCode},
		[]mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentOpenCode},
		}},
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 2 {
		t.Fatalf("adapter transitions = %#v", transitions)
	}
	claude := string(findPreparedAfter(t, transitions, claudeLocation(".claude.json")))
	openCode := string(findPreparedAfter(t, transitions, location("opencode.json")))
	if !strings.Contains(claude, `"type": "http"`) ||
		strings.Contains(claude, `"type": "remote"`) ||
		!strings.Contains(openCode, `"type": "remote"`) ||
		strings.Contains(openCode, `"type": "http"`) {
		t.Fatalf("dialects crossed: Claude=%s OpenCode=%s", claude, openCode)
	}
}

func TestPrepareClaudeUsesImmutableSnapshots(t *testing.T) {
	config := []byte(`{"mcpServers":{},"keep":true}`)
	host := claudePreparedHost(config, nil)
	inspection := inspectClaudePrepared(t, host)
	reads := host.reads
	host.entries[claudeLocation(".claude.json")].Content[0] = '['

	first, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, claudeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	exposed := first.Transitions()
	findPreparedMutation(t, exposed, claudeLocation(".claude.json")).After.Content[0] = '['
	second, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, claudeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if host.reads != reads || findPreparedAfter(
		t, second.Transitions(), claudeLocation(".claude.json"),
	)[0] != '{' {
		t.Fatalf("preparation was not immutable: reads=%d", host.reads)
	}
}

func inspectClaudePrepared(t *testing.T, host *fakeHost) mcpconfiguration.Inspection {
	t.Helper()
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{claudeProjection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	return inspection
}

func claudeSelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentClaudeCode},
	}}
}

func claudePreparedHost(config, registry []byte) *fakeHost {
	result := &fakeHost{entries: make(map[domain.Location]hostfs.Entry)}
	if config != nil {
		result.entries[claudeLocation(".claude.json")] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), config...),
			Mode: 0o644, Device: 9, Inode: 201,
		}
	}
	if registry != nil {
		result.entries[domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		}] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), registry...),
			Mode: 0o600, Device: 9, Inode: 202,
		}
	}
	return result
}

func claudeMutationAt(
	t *testing.T,
	transition configuration.Transition,
	target domain.Location,
) configuration.FileMutation {
	t.Helper()
	for _, mutation := range transition.Mutations {
		if mutation.Target == target {
			return mutation
		}
	}
	t.Fatalf("mutation for %v is absent: %#v", target, transition)
	return configuration.FileMutation{}
}

func assertClaudeMutation(
	t *testing.T,
	mutation configuration.FileMutation,
	before []byte,
	mode uint32,
	inode uint64,
	wantAfter string,
) {
	t.Helper()
	digest := sha256.Sum256(before)
	if mutation.Target != claudeLocation(".claude.json") ||
		!mutation.Before.Exists ||
		mutation.Before.SHA256 != hex.EncodeToString(digest[:]) ||
		mutation.Before.Mode != mode || mutation.Before.Device != 9 ||
		mutation.Before.Inode != inode || mutation.After.Mode != mode&0o600 ||
		string(mutation.After.Content) != wantAfter {
		t.Fatalf("mutation = %#v", mutation)
	}
}
