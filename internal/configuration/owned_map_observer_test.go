package configuration_test

import (
	"errors"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ownedObservationCase struct {
	entries map[domain.Location]hostfs.Entry
	status  configuration.Status
	reason  configuration.Reason
}

var ownedObservationCases = map[string]ownedObservationCase{
	"matching config and registry": {
		entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"other":true,"permission":{"bash":{"*":"allow"}}}`),
			},
			location("opencode.json.mainframe-permissions.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"version":1,"actions":{"bash":{"*":"allow"}}}`),
			},
		},
		status: configuration.Ready,
		reason: configuration.JSONFieldsMatch,
	},
	"missing registry does not adopt matching config": {
		entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"permission":{"bash":{"*":"allow"}}}`),
			},
		},
		status: configuration.NeedsChange,
		reason: configuration.JSONFieldsDrifted,
	},
	"user override is relinquished": {
		entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"permission":{"bash":{"custom *":"deny"}}}`),
			},
			location("opencode.json.mainframe-permissions.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"version":1,"actions":{"bash":{"*":"allow"}}}`),
			},
		},
		status: configuration.NeedsChange,
		reason: configuration.JSONFieldsDrifted,
	},
	"settled tombstone preserves user override": {
		entries: map[domain.Location]hostfs.Entry{
			location("opencode.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"permission":{"bash":{"custom *":"deny"}}}`),
			},
			location("opencode.json.mainframe-permissions.json"): {
				Kind:    hostfs.EntryRegular,
				Content: []byte(`{"version":1,"actions":{"bash":null}}`),
			},
		},
		status: configuration.Ready,
		reason: configuration.JSONFieldsMatch,
	},
}

func TestObserveOwnedMapRequiresBothDocumentsAtTheirSafeFixedPoint(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	resource := ownedMapResource(target, registry)

	for name, test := range ownedObservationCases {
		t.Run(name, func(t *testing.T) {
			assertOwnedObservationCase(t, resource, test, target, registry)
		})
	}
}

func TestObserveOwnedMapDetectsChangedPatternOrder(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	resource := ownedMapResource(target, registry)
	resource.JSONMapOwnership.DesiredMap =
		`{"bash":{"*":"allow","rm -rf /":"deny"}}`
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: {
			Kind: hostfs.EntryRegular,
			Content: []byte(
				`{"permission":{"bash":{"rm -rf /":"deny","*":"allow"}}}`,
			),
		},
		registry: {
			Kind: hostfs.EntryRegular,
			Content: []byte(
				`{"version":1,"actions":{"bash":{"rm -rf /":"deny","*":"allow"}}}`,
			),
		},
	}}

	got, err := configuration.Observe([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := observation(
		"permissions",
		configuration.NeedsChange,
		configuration.JSONFieldsDrifted,
	)
	if !reflect.DeepEqual(got[0], want) {
		t.Fatalf("observation = %#v, want %#v", got[0], want)
	}
}

func assertOwnedObservationCase(
	t *testing.T,
	resource releasecontract.Resource,
	test ownedObservationCase,
	target, registry domain.Location,
) {
	t.Helper()
	host := &fakeHost{entries: test.entries}
	got, err := configuration.Observe([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := observation("permissions", test.status, test.reason)
	if !reflect.DeepEqual(got[0], want) {
		t.Fatalf("observation = %#v, want %#v", got[0], want)
	}
	if host.calls[target] != 1 || host.calls[registry] != 1 {
		t.Fatalf(
			"inspection counts = config:%d registry:%d",
			host.calls[target],
			host.calls[registry],
		)
	}
}

type unsafeRegistryCase struct {
	entry   hostfs.Entry
	failure error
	reason  configuration.Reason
}

var unsafeRegistryCases = map[string]unsafeRegistryCase{
	"duplicate key": {
		entry: hostfs.Entry{
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":1,"version":1,"actions":{}}`),
		},
		reason: configuration.JSONDocumentInvalid,
	},
	"wrong version": {
		entry: hostfs.Entry{
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":2,"actions":{}}`),
		},
		reason: configuration.JSONDocumentInvalid,
	},
	"invalid owned decision": {
		entry: hostfs.Entry{
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":1,"actions":{"bash":"invalid"}}`),
		},
		reason: configuration.JSONDocumentInvalid,
	},
	"empty pattern rule": {
		entry: hostfs.Entry{
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":1,"actions":{"bash":{}}}`),
		},
		reason: configuration.JSONDocumentInvalid,
	},
	"symbolic link": {
		entry:  hostfs.Entry{Kind: hostfs.EntrySymlink},
		reason: configuration.SymbolicLink,
	},
	"wrong kind": {
		entry:  hostfs.Entry{Kind: hostfs.EntryDirectory},
		reason: configuration.WrongKind,
	},
	"inspection failure": {
		failure: errors.New("permission denied"),
		reason:  configuration.InspectionFailed,
	},
}

func TestObserveOwnedMapRejectsUnsafeRegistryState(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	base := map[domain.Location]hostfs.Entry{
		target: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"permission":{"bash":{"*":"allow"}}}`),
		},
	}

	for name, test := range unsafeRegistryCases {
		t.Run(name, func(t *testing.T) {
			entries := map[domain.Location]hostfs.Entry{}
			for key, value := range base {
				entries[key] = value
			}
			if test.failure == nil {
				entries[registry] = test.entry
			}
			host := &fakeHost{
				entries: entries,
				failures: map[domain.Location]error{
					registry: test.failure,
				},
			}
			got, err := configuration.Observe(
				[]releasecontract.Resource{ownedMapResource(target, registry)},
				host,
			)
			if err != nil {
				t.Fatalf("Observe() error = %v", err)
			}
			want := observation("permissions", configuration.Attention, test.reason)
			if !reflect.DeepEqual(got[0], want) {
				t.Fatalf("observation = %#v, want %#v", got[0], want)
			}
		})
	}
}

func TestObserveOwnedMapTreatsMissingDocumentsAsEmpty(t *testing.T) {
	resource := ownedMapResource(
		location("opencode.json"),
		location("opencode.json.mainframe-permissions.json"),
	)
	host := &fakeHost{
		entries:  map[domain.Location]hostfs.Entry{},
		failures: map[domain.Location]error{},
	}

	got, err := configuration.Observe([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := observation(
		"permissions",
		configuration.NeedsChange,
		configuration.JSONFieldsDrifted,
	)
	if !reflect.DeepEqual(got[0], want) {
		t.Fatalf("observation = %#v, want %#v", got[0], want)
	}
}

func TestObserveRejectsOwnershipRegistryTargetCollisions(t *testing.T) {
	registry := location("opencode.json.mainframe-permissions.json")
	first := ownedMapResource(location("opencode.json"), registry)
	second := ownedMapResource(location("other.json"), registry)
	second.ID = "other-permissions"
	seed := resource(
		"state",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	seed.Target = registry

	for name, resources := range map[string][]releasecontract.Resource{
		"registry and resource": {first, seed},
		"duplicate registries":  {first, second},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := configuration.Observe(resources, &fakeHost{}); err == nil {
				t.Fatal("Observe() accepted ownership registry collision")
			}
		})
	}
}

func TestObserveRejectsOverlappingOwnershipMapClaims(t *testing.T) {
	target := location("opencode.json")
	first := ownedMapResource(
		target,
		location("opencode.json.mainframe-permissions.json"),
	)
	static := withJSON(
		resource(
			"static-permission",
			releasecontract.StrategyJSONKeyMerge,
			releasecontract.SupportSupported,
		),
		target,
		releasecontract.JSONField{
			Pointer: "/permission/bash",
			Desired: `"allow"`,
		},
	)
	second := ownedMapResource(
		target,
		location("opencode.json.second-permissions.json"),
	)
	second.ID = "second-permissions"
	second.JSONMapOwnership.MapPointer = "/permission/bash"

	for name, resources := range map[string][]releasecontract.Resource{
		"map and static field": {first, static},
		"overlapping maps":     {first, second},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := configuration.Observe(resources, &fakeHost{}); err == nil {
				t.Fatal("Observe() accepted overlapping JSON ownership")
			}
		})
	}
}

func ownedMapResource(
	target domain.Location,
	registry domain.Location,
) releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "permissions",
		ComponentID: "credential-tools",
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Target:      target,
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer:            "/permission",
			EntrySchema:           "decision-rule-v1",
			DesiredMap:            `{"bash":{"*":"allow"}}`,
			RegistryTarget:        registry,
			RegistrySchemaVersion: 1,
			EntriesPointer:        "/actions",
		},
	}
}

func supportedOwnedMapResource(
	target domain.Location,
	registry domain.Location,
) releasecontract.Resource {
	resource := ownedMapResource(target, registry)
	resource.ComponentID = domain.ComponentOpenCode
	resource.Apply = releasecontract.SupportSupported
	return resource
}
