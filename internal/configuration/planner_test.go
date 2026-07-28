package configuration_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ownedPlanCase struct {
	config   string
	registry string
	desired  string
	included []domain.ComponentID
	want     []configuration.Change
}

var ownedPlanCases = map[string]ownedPlanCase{
	"add managed action": {
		config:   `{"permission":{}}`,
		registry: `{"version":1,"actions":{}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
		want: []configuration.Change{ownedChange(
			configuration.ChangeAdd,
			"bash",
		)},
	},
	"update managed action": {
		config:   `{"permission":{"bash":{"*":"ask"}}}`,
		registry: `{"version":1,"actions":{"bash":{"*":"ask"}}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
		want: []configuration.Change{ownedChange(
			configuration.ChangeUpdate,
			"bash",
		)},
	},
	"remove managed action when deselected": {
		config:   `{"permission":{"bash":{"*":"allow"}}}`,
		registry: `{"version":1,"actions":{"bash":{"*":"allow"}}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		want: []configuration.Change{ownedChange(
			configuration.ChangeRemove,
			"bash",
		)},
	},
	"relinquish user override": {
		config:   `{"permission":{"bash":{"custom *":"deny"}}}`,
		registry: `{"version":1,"actions":{"bash":{"*":"allow"}}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
		want: []configuration.Change{ownedChange(
			configuration.ChangeRelinquish,
			"bash",
		)},
	},
	"matching user action is not adopted": {
		config:   `{"permission":{"bash":{"*":"allow"}}}`,
		registry: `{"version":1,"actions":{}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
		want: []configuration.Change{ownedChange(
			configuration.ChangeRelinquish,
			"bash",
		)},
	},
	"fixed point has no changes": {
		config:   `{"permission":{"bash":{"*":"allow"}}}`,
		registry: `{"version":1,"actions":{"bash":{"*":"allow"}}}`,
		desired:  `{"bash":{"*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
	},
	"deselection retains user override tombstone": {
		config:   `{"permission":{"bash":{"custom *":"deny"}}}`,
		registry: `{"version":1,"actions":{"bash":null}}`,
		desired:  `{"bash":{"*":"allow"}}`,
	},
	"pattern order change updates managed action": {
		config: `{"permission":{"bash":{"*":"allow","rm -rf /":"deny"}}}`,
		registry: `{"version":1,"actions":` +
			`{"bash":{"*":"allow","rm -rf /":"deny"}}}`,
		desired:  `{"bash":{"rm -rf /":"deny","*":"allow"}}`,
		included: []domain.ComponentID{"credential-tools"},
		want: []configuration.Change{ownedChange(
			configuration.ChangeUpdate,
			"bash",
		)},
	},
}

func TestInspectionPlansOwnedMapChanges(t *testing.T) {
	for name, test := range ownedPlanCases {
		t.Run(name, func(t *testing.T) {
			assertOwnedPlanCase(t, test)
		})
	}
}

func assertOwnedPlanCase(t *testing.T, test ownedPlanCase) {
	t.Helper()
	inspection := inspectOwnedMap(
		t,
		test.config,
		test.registry,
		test.desired,
	)
	got, err := inspection.Plan(test.included)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if !reflect.DeepEqual(got.Changes, test.want) {
		t.Fatalf("changes = %#v, want %#v", got.Changes, test.want)
	}
	if len(got.Issues) != 0 {
		t.Fatalf("issues = %#v, want none", got.Issues)
	}
}

func TestInspectionPlansGenericResourcesWithoutClaimingRemoval(t *testing.T) {
	missing := resource(
		"missing",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	present := resource(
		"present",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		present.Target: {Kind: hostfs.EntryRegular},
	}}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{missing, present},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	selected, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("selected Plan() error = %v", err)
	}
	wantChange := configuration.Change{
		ResourceID:  "missing",
		ComponentID: "credential-tools",
		Kind:        configuration.ChangeAdd,
	}
	if !reflect.DeepEqual(selected.Changes, []configuration.Change{wantChange}) {
		t.Fatalf("selected changes = %#v", selected.Changes)
	}

	deselected, err := inspection.Plan(nil)
	if err != nil {
		t.Fatalf("deselected Plan() error = %v", err)
	}
	wantIssue := configuration.Issue{
		ResourceID:  "present",
		ComponentID: "credential-tools",
		Kind:        configuration.IssueRemovalUnsupported,
		Reason:      configuration.ResourceExists,
	}
	if !reflect.DeepEqual(deselected.Issues, []configuration.Issue{wantIssue}) {
		t.Fatalf("deselected issues = %#v, want %#v", deselected.Issues, wantIssue)
	}
}

func TestInspectionPreservesUnsafeGenericObservationsAsIssues(t *testing.T) {
	attention := resource(
		"attention",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	unassessed := resource(
		"unassessed",
		releasecontract.StrategyJSONKeyMerge,
		releasecontract.SupportUnimplemented,
	)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		attention.Target: {Kind: hostfs.EntrySymlink},
	}}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{unassessed, attention},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	got, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	want := []configuration.Issue{
		{
			ResourceID: "attention", ComponentID: "credential-tools",
			Kind: configuration.IssueAttention, Reason: configuration.SymbolicLink,
		},
		{
			ResourceID: "unassessed", ComponentID: "credential-tools",
			Kind:   configuration.IssueNotAssessed,
			Reason: configuration.ObservationUnsupported,
		},
	}
	if !reflect.DeepEqual(got.Issues, want) {
		t.Fatalf("issues = %#v, want %#v", got.Issues, want)
	}
}

func TestInspectionIgnoresUnsupportedGenericResourceWhenUnselected(t *testing.T) {
	input := resource(
		"unassessed",
		releasecontract.StrategyJSONKeyMerge,
		releasecontract.SupportUnimplemented,
	)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{input},
		&fakeHost{},
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	plan, err := inspection.Plan(nil)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if len(plan.Issues) != 0 {
		t.Fatalf("issues = %#v", plan.Issues)
	}
}

func TestInspectionIsImmutableAndPlanningPerformsNoHostReads(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	input := ownedMapResource(target, registry)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"permission":{}}`),
		},
		registry: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":1,"actions":{}}`),
		},
	}}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{input},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	input.JSONMapOwnership.DesiredMap = `{"edit":"deny"}`
	input.LegacySourceSuffixes = append(input.LegacySourceSuffixes, "forged")
	resources := inspection.Resources()
	resources[0].JSONMapOwnership.DesiredMap = `{"write":"ask"}`
	resources[0].LegacySourceSuffixes = append(
		resources[0].LegacySourceSuffixes,
		"returned-forged",
	)
	observations := inspection.Observations()
	observations[0].ResourceID = "forged"
	calls := host.calls[target] + host.calls[registry]

	for attempt := 0; attempt < 2; attempt++ {
		got, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
		if err != nil {
			t.Fatalf("Plan() error = %v", err)
		}
		want := []configuration.Change{
			ownedChange(configuration.ChangeAdd, "bash"),
		}
		if !reflect.DeepEqual(got.Changes, want) {
			t.Fatalf("changes = %#v, want %#v", got.Changes, want)
		}
	}
	if host.calls[target]+host.calls[registry] != calls {
		t.Fatal("planning performed additional host reads")
	}
	if inspection.Observations()[0].ResourceID != "permissions" {
		t.Fatal("returned observations mutated the inspection")
	}
}

func TestInspectionReportsUnsafeOwnedMapAsIssue(t *testing.T) {
	target := location("opencode.json")
	registry := location("opencode.json.mainframe-permissions.json")
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"permission":{}}`),
		},
		registry: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(`{"version":2,"actions":{}}`),
		},
	}}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{ownedMapResource(target, registry)},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	got, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	want := configuration.Issue{
		ResourceID:  "permissions",
		ComponentID: "credential-tools",
		Kind:        configuration.IssueAttention,
		Reason:      configuration.JSONDocumentInvalid,
	}
	if !reflect.DeepEqual(got.Issues, []configuration.Issue{want}) {
		t.Fatalf("issues = %#v, want %#v", got.Issues, want)
	}
	if len(got.Changes) != 0 {
		t.Fatalf("unsafe state produced changes: %#v", got.Changes)
	}
}

func inspectOwnedMap(
	t *testing.T,
	config string,
	registry string,
	desired string,
) configuration.Inspection {
	t.Helper()
	target := location("opencode.json")
	registryTarget := location("opencode.json.mainframe-permissions.json")
	resource := ownedMapResource(target, registryTarget)
	resource.JSONMapOwnership.DesiredMap = desired
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(config),
		},
		registryTarget: {
			Kind:    hostfs.EntryRegular,
			Content: []byte(registry),
		},
	}}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	return inspection
}

func ownedChange(
	kind configuration.ChangeKind,
	unit string,
) configuration.Change {
	return configuration.Change{
		ResourceID:  "permissions",
		ComponentID: "credential-tools",
		UnitID:      unit,
		Kind:        kind,
	}
}
