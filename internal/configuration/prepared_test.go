package configuration_test

import (
	"crypto/sha256"
	"encoding/hex"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

var preparedConfigAfter = strings.Join([]string{
	"{",
	`  "theme": "dark",`,
	`  "permission": {`,
	`    "custom_*": "deny",`,
	`    "bash": {`,
	`      "*": "allow"`,
	"    },",
	`    "edit": "deny"`,
	"  },",
	`  "other": {`,
	`    "keep": true`,
	"  }",
	"}",
	"",
}, "\n")

var preparedRegistryAfter = strings.Join([]string{
	"{",
	`  "version": 1,`,
	`  "actions": {`,
	`    "bash": {`,
	`      "*": "allow"`,
	"    },",
	`    "custom_*": null,`,
	`    "edit": "deny"`,
	"  }",
	"}",
	"",
}, "\n")

func TestInspectionPreparesOneOrderedOwnedMapTransition(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	resource := ownedMapResource(target, registry)
	resource.JSONMapOwnership.DesiredMap =
		`{"edit":"deny","bash":{"*":"allow"}}`
	configRaw := []byte(
		`{"theme":"dark","permission":{"custom_*":"deny",` +
			`"bash":{"*":"ask"}},"other":{"keep":true}}`,
	)
	registryRaw := []byte(
		`{"version":1,"actions":{"bash":{"*":"ask"}}}`,
	)
	host := preparedHost(map[domain.Location]hostfs.Entry{
		target:   preparedEntry(configRaw, 0o644, 11),
		registry: preparedEntry(registryRaw, 0o600, 12),
	})
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	prepared, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 ||
		!reflect.DeepEqual(transitions[0].ResourceIDs, []string{"permissions"}) {
		t.Fatalf("transitions = %#v", transitions)
	}
	mutations := transitions[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	assertPreparedMutation(
		t,
		mutations[0],
		target,
		configRaw,
		0o644,
		11,
		preparedConfigAfter,
	)
	assertPreparedMutation(
		t,
		mutations[1],
		registry,
		registryRaw,
		0o600,
		12,
		preparedRegistryAfter,
	)
}

func TestInspectionPrepareRelinquishOnlyMutatesRegistry(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	configRaw := []byte(
		`{"permission":{"bash":{"custom *":"deny"}}}`,
	)
	registryRaw := []byte(
		`{"version":1,"actions":{"bash":{"*":"allow"}}}`,
	)
	inspection := inspectPreparedOwnedMap(
		t,
		[]releasecontract.Resource{ownedMapResource(target, registry)},
		map[domain.Location]hostfs.Entry{
			target:   preparedEntry(configRaw, 0o600, 21),
			registry: preparedEntry(registryRaw, 0o600, 22),
		},
	)

	prepared, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 1 || mutations[0].Target != registry {
		t.Fatalf("mutations = %#v, want registry only", mutations)
	}
	if strings.Contains(string(mutations[0].After), `"custom *"`) {
		t.Fatalf("registry adopted user rule: %s", mutations[0].After)
	}
}

func TestInspectionPrepareComposesSharedPhysicalTarget(t *testing.T) {
	target := location("opencode.json")
	firstRegistry := location("opencode.json.mainframe-permissions.json")
	secondRegistry := location("opencode.json.mainframe-agent-permissions.json")
	first := ownedMapResource(target, firstRegistry)
	second := ownedMapResource(target, secondRegistry)
	second.ID = "agent-permissions"
	second.JSONMapOwnership.MapPointer = "/agent_permission"
	second.JSONMapOwnership.DesiredMap = `{"task":"deny"}`
	configRaw := []byte(`{"permission":{},"agent_permission":{},"user":true}`)
	inspection := inspectPreparedOwnedMap(
		t,
		[]releasecontract.Resource{first, second},
		map[domain.Location]hostfs.Entry{
			target:         preparedEntry(configRaw, 0o600, 31),
			firstRegistry:  preparedEntry([]byte(`{"version":1,"actions":{}}`), 0o600, 32),
			secondRegistry: preparedEntry([]byte(`{"version":1,"actions":{}}`), 0o600, 33),
		},
	)

	prepared, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 3 {
		t.Fatalf("transitions = %#v", transitions)
	}
	configAfter := string(transitions[0].Mutations[0].After)
	for _, expected := range []string{
		`"bash"`,
		`"task"`,
		`"user": true`,
	} {
		if !strings.Contains(configAfter, expected) {
			t.Fatalf("composed config lacks %s:\n%s", expected, configAfter)
		}
	}
}

func TestInspectionPrepareIsImmutableAndPerformsNoHostReads(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	host := preparedHost(map[domain.Location]hostfs.Entry{
		target:   preparedEntry([]byte(`{"permission":{}}`), 0o600, 41),
		registry: preparedEntry([]byte(`{"version":1,"actions":{}}`), 0o600, 42),
	})
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{ownedMapResource(target, registry)},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	host.entries[target].Content[0] = '['
	calls := host.calls[target] + host.calls[registry]
	first, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	exposed := first.Transitions()
	exposed[0].ResourceIDs[0] = "forged"
	exposed[0].Mutations[0].After[0] = '['

	second, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("second Prepare() error = %v", err)
	}
	if reflect.DeepEqual(exposed, second.Transitions()) {
		t.Fatal("returned mutations alias the immutable plan")
	}
	if host.calls[target]+host.calls[registry] != calls {
		t.Fatal("preparation performed additional host reads")
	}
}

func TestInspectionPrepareFailsClosed(t *testing.T) {
	unsupported := resource(
		"seed",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	unsafe := ownedMapResource(
		location("opencode.json"),
		location("opencode.json.mainframe-permissions.json"),
	)
	tests := map[string]struct {
		resources []releasecontract.Resource
		entries   map[domain.Location]hostfs.Entry
	}{
		"unsupported change": {
			resources: []releasecontract.Resource{unsupported},
		},
		"semantic issue": {
			resources: []releasecontract.Resource{unsafe},
			entries: map[domain.Location]hostfs.Entry{
				unsafe.Target: {Kind: hostfs.EntrySymlink},
			},
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			inspection, err := configuration.Inspect(
				test.resources,
				preparedHost(test.entries),
			)
			if err != nil {
				t.Fatalf("Inspect() error = %v", err)
			}
			prepared, err := inspection.Prepare(
				[]domain.ComponentID{"credential-tools"},
			)
			if err == nil || len(prepared.Transitions()) != 0 {
				t.Fatalf("Prepare() = %#v, %v; want error and zero plan", prepared, err)
			}
		})
	}
}

func assertPreparedMutation(
	t *testing.T,
	mutation configuration.FileMutation,
	target domain.Location,
	before []byte,
	mode uint32,
	inode uint64,
	after string,
) {
	t.Helper()
	digest := sha256.Sum256(before)
	if mutation.Target != target ||
		!mutation.Before.Exists ||
		mutation.Before.SHA256 != hex.EncodeToString(digest[:]) ||
		mutation.Before.Mode != mode ||
		mutation.Before.Device != 7 ||
		mutation.Before.Inode != inode ||
		mutation.Mode != mode&0o600 ||
		string(mutation.After) != after {
		t.Fatalf("mutation = %#v, after =\n%s", mutation, mutation.After)
	}
}

func assertAliasedPreparationFails(
	t *testing.T,
	resources []releasecontract.Resource,
	entries map[domain.Location]hostfs.Entry,
) {
	t.Helper()
	inspection := inspectPreparedOwnedMap(t, resources, entries)
	prepared, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err == nil || len(prepared.Transitions()) != 0 {
		t.Fatalf("Prepare() = %#v, %v; want alias rejection", prepared, err)
	}
}

func inspectPreparedOwnedMap(
	t *testing.T,
	resources []releasecontract.Resource,
	entries map[domain.Location]hostfs.Entry,
) configuration.Inspection {
	t.Helper()
	inspection, err := configuration.Inspect(resources, preparedHost(entries))
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	return inspection
}

func preparedHost(entries map[domain.Location]hostfs.Entry) *fakeHost {
	return &fakeHost{entries: entries}
}

func preparedEntry(
	content []byte,
	mode uint32,
	inode uint64,
) hostfs.Entry {
	return hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: content,
		Mode: mode, Device: 7, Inode: inode,
	}
}
