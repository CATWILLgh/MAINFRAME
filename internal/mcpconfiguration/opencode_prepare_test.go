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

func TestPrepareOpenCodeAddPreservesOrderedUnrelatedJSON(t *testing.T) {
	config := []byte(`{"theme":"dark","permission":{"bash":"ask"},"mcp":{},"user":true}`)
	host := openCodePreparedHost(config, nil)
	inspection := inspectOpenCodePrepared(t, host)

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode},
		openCodeSelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 ||
		!reflect.DeepEqual(transitions[0].ResourceIDs, []string{"opencode.mcp.context7"}) {
		t.Fatalf("transitions = %#v", transitions)
	}
	mutations := transitions[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	want := strings.Join([]string{
		"{",
		`  "theme": "dark",`,
		`  "permission": {`,
		`    "bash": "ask"`,
		"  },",
		`  "mcp": {`,
		`    "context7": {`,
		`      "type": "remote",`,
		`      "url": "https://mcp.context7.com/mcp"`,
		"    }",
		"  },",
		`  "user": true`,
		"}",
		"",
	}, "\n")
	assertOpenCodeMutation(
		t, mutations[0], location("opencode.json"), config, 0o644, 101, want,
	)
	if !strings.Contains(string(mutations[1].After), `"context7": {`) ||
		!strings.Contains(string(mutations[1].After), `"type": "remote"`) {
		t.Fatalf("registry after-image =\n%s", mutations[1].After)
	}
}

func TestPrepareOpenCodeCreatesMissingFilesPrivately(t *testing.T) {
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(nil, nil))
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	for _, mutation := range mutations {
		if mutation.Before.Exists || mutation.Mode != 0o600 {
			t.Fatalf("missing-file mutation = %#v", mutation)
		}
	}
}

type openCodeStateCase struct {
	name       string
	config     string
	registry   string
	selections []mcpcatalog.Selection
	wantCount  int
	wantConfig string
	wantOwned  string
}

func TestPrepareOpenCodeReconcilesOwnedStates(t *testing.T) {
	old := `{"type":"remote","url":"https://old.example/mcp"}`
	tests := []openCodeStateCase{
		{
			name: "update", config: `{"mcp":{"context7":` + old + `},"keep":true}`,
			registry: owned(old), selections: openCodeSelection(), wantCount: 2,
			wantConfig: `"url": "https://mcp.context7.com/mcp"`, wantOwned: `"context7": {`,
		},
		{
			name: "remove", config: `{"mcp":{"context7":` + desired + `},"keep":true}`,
			registry: owned(desired), wantCount: 2,
			wantConfig: `"mcp": {}`, wantOwned: `"servers": {}`,
		},
		{
			name: "relinquish", config: `{"mcp":{"context7":{"type":"remote","url":"https://user.example/mcp"}}}`,
			registry: owned(desired), selections: openCodeSelection(), wantCount: 1,
			wantOwned: `"context7": null`,
		},
		{
			name: "ready", config: `{"mcp":{"context7":` + desired + `}}`,
			registry: owned(desired), selections: openCodeSelection(), wantCount: 0,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			assertOpenCodePreparedState(t, test)
		})
	}
}

func assertOpenCodePreparedState(t *testing.T, test openCodeStateCase) {
	t.Helper()
	inspection := inspectOpenCodePrepared(
		t, openCodePreparedHost([]byte(test.config), []byte(test.registry)),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, test.selections,
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
	mutations := transitions[0].Mutations
	if len(mutations) != test.wantCount {
		t.Fatalf("mutations = %#v", mutations)
	}
	if test.wantConfig != "" && !strings.Contains(string(mutations[0].After), test.wantConfig) {
		t.Fatalf("config after-image =\n%s", mutations[0].After)
	}
	if !strings.Contains(string(mutations[len(mutations)-1].After), test.wantOwned) {
		t.Fatalf("registry after-image =\n%s", mutations[len(mutations)-1].After)
	}
}

func TestPrepareOpenCodeOntoComposesSharedTarget(t *testing.T) {
	configTarget := location("opencode.json")
	permissionRegistry := location("opencode.json.mainframe-permissions.json")
	config := []byte(`{"theme":"dark","permission":{},"mcp":{},"user":true}`)
	host := openCodePreparedHost(config, nil)
	host.entries[permissionRegistry] = preparedOpenCodeEntry(
		[]byte(`{"version":1,"actions":{}}`), 0o600, 103,
	)
	genericInspection, err := configuration.Inspect(
		[]releasecontract.Resource{openCodePermissionResource(configTarget, permissionRegistry)},
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	base, err := genericInspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection := inspectOpenCodePrepared(t, host)

	prepared, err := mcpInspection.PrepareOnto(
		base, []domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
	)
	if err != nil {
		t.Fatalf("PrepareOnto() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 3 ||
		!reflect.DeepEqual(
			transitions[0].ResourceIDs,
			[]string{"opencode.mcp.context7", "opencode.permissions"},
		) {
		t.Fatalf("composed transitions = %#v", transitions)
	}
	after := string(transitions[0].Mutations[0].After)
	for _, expected := range []string{`"bash": "deny"`, `"context7": {`, `"user": true`} {
		if !strings.Contains(after, expected) {
			t.Fatalf("composed config lacks %s:\n%s", expected, after)
		}
	}
}

func TestPrepareOpenCodeOntoFailsClosedAtCompositionBoundary(t *testing.T) {
	config := []byte(`{"mcp":{}}`)
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(config, nil))

	t.Run("different before image", func(t *testing.T) {
		base := preparedBasePlan(t, location("opencode.json"), []byte(`{"permission":{}}`))
		if _, err := inspection.PrepareOnto(
			base, []domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
		); err == nil {
			t.Fatal("PrepareOnto() accepted a different before-image")
		}
	})

	t.Run("registry already mutated", func(t *testing.T) {
		base := preparedBasePlan(
			t,
			location("opencode.json.mainframe-mcp.json"),
			[]byte(`{"version":1,"servers":{}}`),
		)
		if _, err := inspection.PrepareOnto(
			base, []domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
		); err == nil {
			t.Fatal("PrepareOnto() overwrote an existing registry mutation")
		}
	})
}

func TestPrepareOpenCodeUsesImmutableSnapshots(t *testing.T) {
	config := []byte(`{"mcp":{},"keep":true}`)
	host := openCodePreparedHost(config, nil)
	inspection := inspectOpenCodePrepared(t, host)
	reads := host.reads
	host.entries[location("opencode.json")].Content[0] = '['

	first, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	exposed := first.Transitions()
	exposed[0].Mutations[0].After[0] = '['
	second, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if host.reads != reads || second.Transitions()[0].Mutations[0].After[0] != '{' {
		t.Fatalf("preparation was not immutable: reads=%d", host.reads)
	}
}

func inspectOpenCodePrepared(t *testing.T, host *fakeHost) mcpconfiguration.Inspection {
	t.Helper()
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	return inspection
}

func openCodeSelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentOpenCode},
	}}
}

func openCodePreparedHost(config, registry []byte) *fakeHost {
	result := &fakeHost{entries: make(map[domain.Location]hostfs.Entry)}
	if config != nil {
		result.entries[location("opencode.json")] = preparedOpenCodeEntry(config, 0o644, 101)
	}
	if registry != nil {
		result.entries[location("opencode.json.mainframe-mcp.json")] = preparedOpenCodeEntry(
			registry, 0o600, 102,
		)
	}
	return result
}

func preparedOpenCodeEntry(raw []byte, mode uint32, inode uint64) hostfs.Entry {
	return hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: append([]byte(nil), raw...),
		Mode: mode, Device: 7, Inode: inode,
	}
}

func openCodePermissionResource(
	target domain.Location,
	registry domain.Location,
) releasecontract.Resource {
	return releasecontract.Resource{
		ID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
		Strategy: releasecontract.StrategyJSONKeyMerge, Target: target,
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportSupported,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer: "/permission", DesiredMap: `{"bash":"deny"}`,
			RegistryTarget: registry, RegistrySchemaVersion: 1,
			EntriesPointer: "/actions", EntrySchema: "decision-rule-v1",
		},
	}
}

func preparedBasePlan(
	t *testing.T,
	target domain.Location,
	observed []byte,
) configuration.PreparedPlan {
	t.Helper()
	digest := sha256.Sum256(observed)
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{"opencode.permissions"},
		Mutations: []configuration.FileMutation{{
			Target: target,
			Before: configuration.BeforeImage{
				Exists: true, SHA256: hex.EncodeToString(digest[:]),
				Mode: 0o644, Device: 7, Inode: 101,
			},
			After: []byte(`{"permission":{"bash":"deny"}}`), Mode: 0o600,
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}
	return plan
}

func assertOpenCodeMutation(
	t *testing.T,
	mutation configuration.FileMutation,
	target domain.Location,
	before []byte,
	mode uint32,
	inode uint64,
	wantAfter string,
) {
	t.Helper()
	digest := sha256.Sum256(before)
	if mutation.Target != target || !mutation.Before.Exists ||
		mutation.Before.SHA256 != hex.EncodeToString(digest[:]) ||
		mutation.Before.Mode != mode || mutation.Before.Device != 7 ||
		mutation.Before.Inode != inode || mutation.Mode != mode&0o600 ||
		string(mutation.After) != wantAfter {
		t.Fatalf("mutation = %#v", mutation)
	}
}
