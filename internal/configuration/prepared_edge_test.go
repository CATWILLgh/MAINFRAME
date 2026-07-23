package configuration_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectionPrepareCreatesPrivateMissingFiles(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{supportedOwnedMapResource(target, registry)},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	for _, mutation := range mutations {
		if mutation.Before.Exists || mutation.Before.SHA256 != "" ||
			mutation.After.Mode != 0o600 {
			t.Fatalf("missing-file mutation = %#v", mutation)
		}
	}
}

func TestInspectionPrepareCreatesSelectedEmptyOwnedMap(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	resource := supportedOwnedMapResource(target, registry)
	resource.JSONMapOwnership.DesiredMap = `{}`
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 2 {
		t.Fatalf("empty selected map was not materialized: %#v", transitions)
	}
	if !strings.Contains(
		string(transitions[0].Mutations[0].After.Content),
		`"permission": {}`,
	) {
		t.Fatalf("configuration map is absent:\n%s", transitions[0].Mutations[0].After.Content)
	}
}

func TestInspectionPrepareRejectsPhysicalTargetAliases(t *testing.T) {
	t.Run("configuration and registry", func(t *testing.T) {
		target := location("opencode.json")
		registry := location("opencode.json.mainframe-permissions.json")
		shared := []byte(`{"version":1,"actions":{}}`)
		assertAliasedPreparationFails(
			t,
			[]releasecontract.Resource{supportedOwnedMapResource(target, registry)},
			map[domain.Location]hostfs.Entry{
				target:   preparedEntry(shared, 0o600, 71),
				registry: preparedEntry(shared, 0o600, 71),
			},
		)
	})
	t.Run("two configuration targets", func(t *testing.T) {
		firstTarget := location("opencode.json")
		secondTarget := location("other-opencode.json")
		first := supportedOwnedMapResource(
			firstTarget,
			location("opencode.json.mainframe-permissions.json"),
		)
		second := supportedOwnedMapResource(
			secondTarget,
			location("other-opencode.json.mainframe-permissions.json"),
		)
		second.ID = "other-permissions"
		second.JSONMapOwnership.MapPointer = "/agent_permission"
		second.JSONMapOwnership.DesiredMap = `{"task":"deny"}`
		shared := []byte(`{"permission":{},"agent_permission":{}}`)
		assertAliasedPreparationFails(
			t,
			[]releasecontract.Resource{first, second},
			map[domain.Location]hostfs.Entry{
				firstTarget:  preparedEntry(shared, 0o600, 81),
				secondTarget: preparedEntry(shared, 0o600, 81),
				first.JSONMapOwnership.RegistryTarget: preparedEntry(
					[]byte(`{"version":1,"actions":{}}`),
					0o600,
					82,
				),
				second.JSONMapOwnership.RegistryTarget: preparedEntry(
					[]byte(`{"version":1,"actions":{}}`),
					0o600,
					83,
				),
			},
		)
	})
}

func TestInspectionPrepareRejectsUnsafeExistingMode(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	inspection := inspectPreparedOwnedMap(
		t,
		[]releasecontract.Resource{supportedOwnedMapResource(target, registry)},
		map[domain.Location]hostfs.Entry{
			target:   preparedEntry([]byte(`{"permission":{}}`), 0o200, 51),
			registry: preparedEntry([]byte(`{"version":1,"actions":{}}`), 0o600, 52),
		},
	)

	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err == nil || len(prepared.Transitions()) != 0 {
		t.Fatalf("Prepare() = %#v, %v; want fail-closed mode error", prepared, err)
	}
}

func TestInspectionPrepareFixedPointIsEmpty(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	inspection := inspectPreparedOwnedMap(
		t,
		[]releasecontract.Resource{supportedOwnedMapResource(target, registry)},
		map[domain.Location]hostfs.Entry{
			target: preparedEntry(
				[]byte(`{"permission":{"bash":{"*":"allow"}}}`),
				0o600,
				61,
			),
			registry: preparedEntry(
				[]byte(`{"version":1,"actions":{"bash":{"*":"allow"}}}`),
				0o600,
				62,
			),
		},
	)
	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("fixed point produced transitions: %#v", prepared.Transitions())
	}
}
