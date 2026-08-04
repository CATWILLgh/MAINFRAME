package configuration_test

import (
	"encoding/json"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestJSONClaimsRoundTripPreservesForeignArrayOrderAndScalarPredecessor(t *testing.T) {
	resource := jsonClaimResource()
	config := domain.Location{Root: domain.RootZCodeConfig, Path: "cli/config.json"}
	registry := resource.JSONClaimOwnership.RegistryTarget
	host := claimHost(map[domain.Location][]byte{
		config: []byte(`{"hooks":{"enabled":false,"events":{"SessionStart":[{"matcher":"foreign-before"},{"matcher":"foreign-after"}]}}}`),
	})
	inspection, err := configuration.Inspect([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentZCodeDesktop})
	if err != nil {
		t.Fatalf("Prepare(select) error = %v", err)
	}
	selected := mutationContents(t, prepared)
	assertSelectedClaims(t, selected[config], selected[registry])

	host = claimHost(selected)
	inspection, err = configuration.Inspect([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("Inspect(selected) error = %v", err)
	}
	prepared, err = inspection.Prepare(nil)
	if err != nil {
		t.Fatalf("Prepare(deselect) error = %v", err)
	}
	if !removalTargets(prepared)[registry] {
		t.Fatal("ownership registry was not removed")
	}
	deselected := mutationContents(t, prepared)
	assertDeselectedClaims(t, deselected[config], deselected[registry])
}

func TestJSONClaimDriftRelinquishesWithoutOverwriting(t *testing.T) {
	resource := jsonClaimResource()
	config := resource.Target
	registry := resource.JSONClaimOwnership.RegistryTarget
	initial := claimHost(map[domain.Location][]byte{
		config: []byte(`{"hooks":{"enabled":false,"events":{"SessionStart":[]}}}`),
	})
	inspection, _ := configuration.Inspect([]releasecontract.Resource{resource}, initial)
	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentZCodeDesktop})
	if err != nil {
		t.Fatalf("Prepare(initial) error = %v", err)
	}
	selected := mutationContents(t, prepared)
	var document map[string]any
	if err := json.Unmarshal(selected[config], &document); err != nil {
		t.Fatal(err)
	}
	hooks := document["hooks"].(map[string]any)
	hooks["enabled"] = "user-edited"
	entry := hooks["events"].(map[string]any)["SessionStart"].([]any)[0].(map[string]any)
	entry["user"] = true
	selected[config], _ = json.Marshal(document)

	inspection, err = configuration.Inspect([]releasecontract.Resource{resource}, claimHost(selected))
	if err != nil {
		t.Fatalf("Inspect(drift) error = %v", err)
	}
	prepared, err = inspection.Prepare([]domain.ComponentID{domain.ComponentZCodeDesktop})
	if err != nil {
		t.Fatalf("Prepare(relinquish) error = %v", err)
	}
	relinquished := mutationContents(t, prepared)
	if _, changed := relinquished[config]; changed {
		t.Fatal("drifted user config was overwritten")
	}
	if !containsStates(t, relinquished[registry], "relinquished") {
		t.Fatalf("registry did not record relinquishment: %s", relinquished[registry])
	}
}

func TestJSONClaimDeselectAbsentFilesIsNoop(t *testing.T) {
	resource := jsonClaimResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		claimHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	prepared, err := inspection.Prepare(nil)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("deselect absent files transitions = %#v", prepared.Transitions())
	}
}

func TestJSONClaimDeselectRemovesAdapterCreatedEmptyFiles(t *testing.T) {
	resource := jsonClaimResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		claimHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect(initial) error = %v", err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatalf("Prepare(select) error = %v", err)
	}
	selected := mutationContents(t, prepared)
	inspection, err = configuration.Inspect(
		[]releasecontract.Resource{resource},
		claimHost(selected),
	)
	if err != nil {
		t.Fatalf("Inspect(selected) error = %v", err)
	}
	prepared, err = inspection.Prepare(nil)
	if err != nil {
		t.Fatalf("Prepare(deselect) error = %v", err)
	}
	removed := removalTargets(prepared)
	if !removed[resource.Target] ||
		!removed[resource.JSONClaimOwnership.RegistryTarget] {
		t.Fatalf("removed targets = %#v", removed)
	}
}

func TestJSONClaimRetiredClaimIsReconciledFromRegistryMetadata(t *testing.T) {
	original := jsonClaimResource()
	config := original.Target
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{original},
		claimHost(map[domain.Location][]byte{
			config: []byte(`{"hooks":{"enabled":false,"events":{"SessionStart":[]}}}`),
		}),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatal(err)
	}
	selected := mutationContents(t, prepared)
	future := jsonClaimResource()
	future.JSONClaimOwnership.Claims = future.JSONClaimOwnership.Claims[1:]
	inspection, err = configuration.Inspect(
		[]releasecontract.Resource{future},
		claimHost(selected),
	)
	if err != nil {
		t.Fatalf("Inspect(future) error = %v", err)
	}
	prepared, err = inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatalf("Prepare(future) error = %v", err)
	}
	after := mutationContents(t, prepared)
	var document map[string]any
	if err := json.Unmarshal(after[config], &document); err != nil {
		t.Fatal(err)
	}
	entries := document["hooks"].(map[string]any)["events"].(map[string]any)["SessionStart"].([]any)
	if len(entries) != 0 {
		t.Fatalf("retired unchanged entry remains: %#v", entries)
	}
	if bytesContains(after[future.JSONClaimOwnership.RegistryTarget], "\"array\"") {
		t.Fatal("retired registry claim remains")
	}
}

func TestJSONClaimRetiredDriftedEntryIsPreservedAndUntracked(t *testing.T) {
	original := jsonClaimResource()
	inspection, _ := configuration.Inspect(
		[]releasecontract.Resource{original},
		claimHost(map[domain.Location][]byte{
			original.Target: []byte(`{"hooks":{"enabled":false,"events":{"SessionStart":[]}}}`),
		}),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatal(err)
	}
	selected := mutationContents(t, prepared)
	var document map[string]any
	if err := json.Unmarshal(selected[original.Target], &document); err != nil {
		t.Fatal(err)
	}
	hooks := document["hooks"].(map[string]any)
	entry := hooks["events"].(map[string]any)["SessionStart"].([]any)[0].(map[string]any)
	entry["user-edit"] = true
	selected[original.Target], _ = json.Marshal(document)
	future := jsonClaimResource()
	future.JSONClaimOwnership.Claims = future.JSONClaimOwnership.Claims[1:]
	inspection, err = configuration.Inspect(
		[]releasecontract.Resource{future},
		claimHost(selected),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err = inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatal(err)
	}
	after := mutationContents(t, prepared)
	if _, changed := after[future.Target]; changed {
		t.Fatal("retired drifted config entry was overwritten")
	}
	if bytesContains(after[future.JSONClaimOwnership.RegistryTarget], "\"array\"") {
		t.Fatal("retired drifted claim remains tracked")
	}
}

func TestJSONClaimInvalidOrSymlinkedFilesFailBeforeMutation(t *testing.T) {
	resource := jsonClaimResource()
	tests := map[string]map[domain.Location]hostfs.Entry{
		"invalid config": {
			resource.Target: {Kind: hostfs.EntryRegular, Content: []byte(`{`)},
		},
		"symlink config": {
			resource.Target: {Kind: hostfs.EntrySymlink},
		},
		"invalid registry": {
			resource.Target: {Kind: hostfs.EntryRegular, Content: []byte(`{}`)},
			resource.JSONClaimOwnership.RegistryTarget: {
				Kind: hostfs.EntryRegular, Content: []byte(`{"schema_version":1}`),
			},
		},
		"symlink registry": {
			resource.Target: {Kind: hostfs.EntryRegular, Content: []byte(`{}`)},
			resource.JSONClaimOwnership.RegistryTarget: {Kind: hostfs.EntrySymlink},
		},
	}
	for name, entries := range tests {
		t.Run(name, func(t *testing.T) {
			host := &fakeHost{entries: entries}
			inspection, err := configuration.Inspect(
				[]releasecontract.Resource{resource}, host,
			)
			if err != nil {
				t.Fatalf("Inspect() error = %v", err)
			}
			if _, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentZCodeDesktop},
			); err == nil {
				t.Fatal("Prepare() accepted unsafe ownership file")
			}
		})
	}
}

func jsonClaimResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "zcode.hooks", ComponentID: domain.ComponentZCodeDesktop,
		Strategy:   releasecontract.StrategyJSONKeyMerge,
		SourcePath: "config.json", Target: domain.Location{Root: domain.RootZCodeConfig, Path: "cli/config.json"},
		Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportSupported,
		JSONClaimOwnership: &releasecontract.JSONClaimOwnership{
			RegistryTarget:        domain.Location{Root: domain.RootZCodeConfig, Path: "mainframe/config-ownership.json"},
			RegistrySchemaVersion: 1,
			Claims: []releasecontract.JSONClaim{
				{ID: "array", Kind: releasecontract.JSONClaimArrayEntry, Pointer: "/hooks/events/SessionStart", SelectorPointer: "/hooks/0/args/1", SelectorValue: `"SessionStart"`, Desired: `{"hooks":[{"type":"process","args":["_zcode-hook","SessionStart"]}]}`},
				{ID: "scalar", Kind: releasecontract.JSONClaimExactScalar, Pointer: "/hooks/enabled", Desired: `true`},
			},
		},
	}
}

func claimHost(files map[domain.Location][]byte) *fakeHost {
	entries := make(map[domain.Location]hostfs.Entry, len(files))
	for target, content := range files {
		entries[target] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: content, Mode: 0o600,
			Device: 1, Inode: uint64(len(entries) + 1), BirthSeconds: 1,
		}
	}
	return &fakeHost{entries: entries}
}

func mutationContents(t *testing.T, prepared configuration.PreparedPlan) map[domain.Location][]byte {
	t.Helper()
	result := map[domain.Location][]byte{}
	for _, transition := range prepared.Transitions() {
		for _, mutation := range transition.Mutations {
			result[mutation.Target] = mutation.After.Content
		}
	}
	return result
}

func removalTargets(prepared configuration.PreparedPlan) map[domain.Location]bool {
	result := map[domain.Location]bool{}
	for _, transition := range prepared.Transitions() {
		for _, mutation := range transition.Mutations {
			if !mutation.After.Exists {
				result[mutation.Target] = true
			}
		}
	}
	return result
}

func assertSelectedClaims(t *testing.T, config, registry []byte) {
	t.Helper()
	var document map[string]any
	if err := json.Unmarshal(config, &document); err != nil {
		t.Fatal(err)
	}
	hooks := document["hooks"].(map[string]any)
	if hooks["enabled"] != true {
		t.Fatalf("enabled = %#v", hooks["enabled"])
	}
	entries := hooks["events"].(map[string]any)["SessionStart"].([]any)
	if len(entries) != 3 || entries[0].(map[string]any)["matcher"] != "foreign-before" || entries[1].(map[string]any)["matcher"] != "foreign-after" {
		t.Fatalf("foreign entry order changed: %#v", entries)
	}
	if !containsStates(t, registry, "owned") {
		t.Fatalf("invalid owned registry: %s", registry)
	}
}

func assertDeselectedClaims(t *testing.T, config, _ []byte) {
	t.Helper()
	var document map[string]any
	if err := json.Unmarshal(config, &document); err != nil {
		t.Fatal(err)
	}
	hooks := document["hooks"].(map[string]any)
	if hooks["enabled"] != false {
		t.Fatalf("predecessor not restored: %#v", hooks["enabled"])
	}
	entries := hooks["events"].(map[string]any)["SessionStart"].([]any)
	if len(entries) != 2 {
		t.Fatalf("owned array entry not removed: %#v", entries)
	}
}

func containsStates(t *testing.T, payload []byte, needle string) bool {
	t.Helper()
	return len(payload) != 0 && string(payload) != "" && json.Valid(payload) && bytesContains(payload, needle)
}

func bytesContains(payload []byte, needle string) bool {
	for index := 0; index+len(needle) <= len(payload); index++ {
		if string(payload[index:index+len(needle)]) == needle {
			return true
		}
	}
	return false
}
