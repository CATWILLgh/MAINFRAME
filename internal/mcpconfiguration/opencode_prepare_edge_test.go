package mcpconfiguration_test

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareOpenCodeComposesSharedTargetAndRegistryDeterministically(t *testing.T) {
	second := projection()
	second.ID = "opencode.mcp.docs"
	second.ServerID = "docs"
	second.EntryKey = "docs"
	second.DesiredEntry = `{"type":"remote","url":"https://docs.example/mcp"}`
	host := openCodePreparedHost(nil, nil)
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection(), second},
		twoServerCatalog(t),
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	selections := []mcpcatalog.Selection{
		{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		},
		{
			ServerID: "docs", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		},
	}

	first, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, selections,
	)
	if err != nil {
		t.Fatal(err)
	}
	secondPlan, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, selections,
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := first.Transitions()
	if !reflect.DeepEqual(transitions, secondPlan.Transitions()) ||
		len(transitions) != 1 || len(transitions[0].Mutations) != 2 ||
		!reflect.DeepEqual(
			transitions[0].ResourceIDs,
			[]string{"opencode.mcp.context7", "opencode.mcp.docs"},
		) {
		t.Fatalf("shared preparation = %#v", transitions)
	}
	for _, expected := range []string{`"context7": {`, `"docs": {`} {
		if !strings.Contains(string(transitions[0].Mutations[0].After.Content), expected) ||
			!strings.Contains(string(transitions[0].Mutations[1].After.Content), expected) {
			t.Fatalf("shared after-images lack %s: %#v", expected, transitions)
		}
	}
}

func TestPrepareOpenCodeComposesMixedExistingIntents(t *testing.T) {
	oldContext := `{"type":"remote","url":"https://old.example/mcp"}`
	docs := `{"type":"remote","url":"https://docs.example/mcp"}`
	config := []byte(
		`{"mcp":{"context7":` + oldContext + `,"docs":` + docs + `},"keep":true}`,
	)
	registry := []byte(
		`{"version":1,"servers":{"context7":` + oldContext + `,"docs":` + docs + `}}`,
	)
	second := projection()
	second.ID = "opencode.mcp.docs"
	second.ServerID = "docs"
	second.EntryKey = "docs"
	second.DesiredEntry = docs
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection(), second},
		twoServerCatalog(t),
		openCodePreparedHost(config, registry),
	)
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode}, openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 2 ||
		!reflect.DeepEqual(
			transitions[0].ResourceIDs,
			[]string{"opencode.mcp.context7", "opencode.mcp.docs"},
		) {
		t.Fatalf("mixed preparation = %#v", transitions)
	}
	for _, after := range [][]byte{
		transitions[0].Mutations[0].After.Content,
		transitions[0].Mutations[1].After.Content,
	} {
		if strings.Contains(string(after), `"docs"`) ||
			!strings.Contains(string(after), `"https://mcp.context7.com/mcp"`) {
			t.Fatalf("mixed after-image =\n%s", after)
		}
	}
	if !strings.Contains(string(transitions[0].Mutations[0].After.Content), `"keep": true`) {
		t.Fatalf("unrelated JSON was lost:\n%s", transitions[0].Mutations[0].After.Content)
	}
}

func TestPrepareOpenCodeOntoRejectsEveryBeforeImageMismatch(t *testing.T) {
	config := []byte(`{"mcp":{}}`)
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(config, nil))
	exact := openCodeBeforeImage(config, 0o644, 101)
	tests := map[string]configuration.BeforeImage{
		"existence": {},
		"digest": {
			Exists: true, SHA256: openCodeDigest([]byte(`{"different":true}`)),
			Mode: 0o644, Device: 7, Inode: 101,
			BirthSeconds: 102,
		},
		"mode": {
			Exists: true, SHA256: exact.SHA256,
			Mode: 0o400, Device: 7, Inode: 101,
			BirthSeconds: 102,
		},
		"device": {
			Exists: true, SHA256: exact.SHA256,
			Mode: 0o644, Device: 8, Inode: 101,
			BirthSeconds: 102,
		},
		"inode": {
			Exists: true, SHA256: exact.SHA256,
			Mode: 0o644, Device: 7, Inode: 202,
			BirthSeconds: 102,
		},
		"birth": {
			Exists: true, SHA256: exact.SHA256,
			Mode: 0o644, Device: 7, Inode: 101,
			BirthSeconds: 999,
		},
	}
	for name, before := range tests {
		t.Run(name, func(t *testing.T) {
			base := openCodeBasePlan(
				t,
				"opencode.permissions",
				location("opencode.json"),
				before,
				[]byte(`{"permission":{"bash":"deny"},"mcp":{}}`),
			)
			if _, err := inspection.PrepareOnto(
				base,
				[]domain.ComponentID{domain.ComponentOpenCode},
				openCodeSelection(),
			); err == nil {
				t.Fatal("PrepareOnto() accepted mismatched before-image")
			}
		})
	}
}

func TestPrepareOpenCodeOntoRejectsInvalidBaseAfterImage(t *testing.T) {
	config := []byte(`{"mcp":{}}`)
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(config, nil))
	base := openCodeBasePlan(
		t,
		"opencode.permissions",
		location("opencode.json"),
		openCodeBeforeImage(config, 0o644, 101),
		[]byte(`{"mcp":[]}`),
	)
	if _, err := inspection.PrepareOnto(
		base,
		[]domain.ComponentID{domain.ComponentOpenCode},
		openCodeSelection(),
	); err == nil {
		t.Fatal("PrepareOnto() accepted an incompatible base after-image")
	}
}

func TestPrepareOpenCodeOntoPreservesUnrelatedTransition(t *testing.T) {
	config := []byte(`{"mcp":{},"keep":true}`)
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(config, nil))
	shared := configuration.Transition{
		ResourceIDs: []string{"opencode.permissions"},
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      location("opencode.json"),
			Before:      openCodeBeforeImage(config, 0o644, 101),
			After: configuration.AfterImage{
				Exists: true,
				Content: []byte(
					`{"mcp":{},"permission":{"bash":"deny"},"keep":true}`,
				),
				Mode: 0o600,
			},
		}},
	}
	unrelated := configuration.Transition{
		ResourceIDs: []string{"opencode.unrelated"},
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      location("unrelated.json"),
			After: configuration.AfterImage{
				Exists:  true,
				Content: []byte("{\"owned\":true}\n"),
				Mode:    0o600,
			},
		}},
	}
	base, err := configuration.NewPreparedPlan([]configuration.Transition{shared, unrelated})
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := inspection.PrepareOnto(
		base,
		[]domain.ComponentID{domain.ComponentOpenCode},
		openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	var found *configuration.Transition
	for _, transition := range prepared.Transitions() {
		if reflect.DeepEqual(transition.ResourceIDs, unrelated.ResourceIDs) {
			copy := transition
			found = &copy
		}
	}
	if found == nil || !reflect.DeepEqual(*found, unrelated) {
		t.Fatalf("unrelated transition changed: %#v", prepared.Transitions())
	}
}

func TestPrepareOpenCodeRelinquishDoesNotJoinSharedBaseTarget(t *testing.T) {
	config := []byte(`{"mcp":{"context7":{"type":"remote","url":"https://user.example/mcp"}}}`)
	host := openCodePreparedHost(config, []byte(owned(desired)))
	inspection := inspectOpenCodePrepared(t, host)
	base := openCodeBasePlan(
		t,
		"opencode.permissions",
		location("opencode.json"),
		openCodeBeforeImage(config, 0o644, 101),
		[]byte(`{"permission":{"bash":"deny"},"mcp":{"context7":{"type":"remote","url":"https://user.example/mcp"}}}`),
	)

	prepared, err := inspection.PrepareOnto(
		base,
		[]domain.ComponentID{domain.ComponentOpenCode},
		openCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 2 {
		t.Fatalf("relinquish transitions = %#v", transitions)
	}
	for _, transition := range transitions {
		if len(transition.ResourceIDs) != 1 {
			t.Fatalf("unrelated transitions were joined: %#v", transitions)
		}
	}
}

func TestPrepareOpenCodeOntoRejectsCrossPlanPhysicalAlias(t *testing.T) {
	config := []byte(`{"mcp":{}}`)
	registry := []byte(`{"version":1,"servers":{}}`)
	host := openCodePreparedHost(config, registry)
	registryEntry := host.entries[location("opencode.json.mainframe-mcp.json")]
	registryEntry.Inode = 150
	host.entries[location("opencode.json.mainframe-mcp.json")] = registryEntry
	inspection := inspectOpenCodePrepared(t, host)
	unrelated := []byte(`{"owned":true}`)
	base := openCodeBasePlan(
		t,
		"opencode.unrelated",
		location("unrelated.json"),
		openCodeBeforeImage(unrelated, 0o600, 150),
		[]byte(`{"owned":false}`),
	)

	if _, err := inspection.PrepareOnto(
		base,
		[]domain.ComponentID{domain.ComponentOpenCode},
		openCodeSelection(),
	); err == nil {
		t.Fatal("PrepareOnto() accepted a cross-plan physical alias")
	}
}

func openCodeBasePlan(
	t *testing.T,
	resourceID string,
	target domain.Location,
	before configuration.BeforeImage,
	after []byte,
) configuration.PreparedPlan {
	t.Helper()
	mode := uint32(0o600)
	if before.Exists {
		mode = before.Mode & 0o600
	}
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{resourceID},
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      target,
			Before:      before,
			After: configuration.AfterImage{
				Exists:  true,
				Content: append([]byte(nil), after...),
				Mode:    mode,
			},
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}
	return plan
}

func openCodeBeforeImage(
	raw []byte,
	mode uint32,
	inode uint64,
) configuration.BeforeImage {
	return configuration.BeforeImage{
		Exists: true, SHA256: openCodeDigest(raw),
		Mode: mode, Device: 7, Inode: inode,
		BirthSeconds: int64(inode) + 1,
	}
}

func openCodeDigest(raw []byte) string {
	digest := sha256.Sum256(raw)
	return hex.EncodeToString(digest[:])
}

func twoServerCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]any
	if err := json.Unmarshal(payload, &document); err != nil {
		t.Fatal(err)
	}
	servers := document["servers"].([]any)
	encoded, err := json.Marshal(servers[0])
	if err != nil {
		t.Fatal(err)
	}
	var cloned map[string]any
	if err := json.Unmarshal(encoded, &cloned); err != nil {
		t.Fatal(err)
	}
	cloned["id"] = "docs"
	cloned["name"] = "Docs"
	for _, rawProfile := range cloned["profiles"].([]any) {
		rawProfile.(map[string]any)["endpoint"] = "https://docs.example/mcp"
	}
	document["servers"] = append(servers, cloned)
	payload, err = json.Marshal(document)
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatal(err)
	}
	return catalog
}
