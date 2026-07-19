package mcpconfiguration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestDeselectionReconcilesOwnedEntriesAcrossAdapterCodecs(t *testing.T) {
	for _, test := range deselectionCodecCases() {
		t.Run(test.name, func(t *testing.T) {
			inspection := inspectDeselectionCase(t, test.projection, test.ownedEntries)
			plan, err := inspection.PlanWithPreservation(nil, nil, nil)
			if err != nil {
				t.Fatalf("PlanWithPreservation() error = %v", err)
			}
			if plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentRemove {
				t.Fatalf("plan = %#v", plan)
			}
			prepared, err := inspection.PrepareWithPreservation(nil, nil, nil)
			if err != nil {
				t.Fatalf("PrepareWithPreservation() error = %v", err)
			}
			if len(prepared.Transitions()) != 1 {
				t.Fatalf("transitions = %#v", prepared.Transitions())
			}
		})
	}
}

func TestDeselectionRelinquishesUserChangedEntriesAcrossAdapterCodecs(t *testing.T) {
	for _, test := range deselectionCodecCases() {
		states := []struct {
			name    string
			entries map[domain.Location]hostfs.Entry
		}{
			{name: "changed", entries: test.changedEntries},
			{name: "deleted", entries: test.deletedEntries},
		}
		for _, state := range states {
			t.Run(test.name+"/"+state.name, func(t *testing.T) {
				assertDeselectionRelinquishes(t, test.projection, state.entries)
			})
		}
	}
}

func TestDeselectionIgnoresUnownedAndMalformedInactiveState(t *testing.T) {
	tests := []struct {
		name    string
		entries map[domain.Location]hostfs.Entry
	}{
		{name: "unowned exact entry", entries: entries(`{"mcp":{"context7":`+desired+`}}`, "")},
		{name: "malformed unowned config", entries: entries(`{"mcp":`, "")},
		{name: "malformed ownership registry", entries: entries(`{"mcp":{"context7":`+desired+`}}`, `{"version":`)},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			inspection := inspectDeselectionCase(t, projection(), test.entries)
			plan, err := inspection.PlanWithPreservation(nil, nil, nil)
			if err != nil {
				t.Fatalf("PlanWithPreservation() error = %v", err)
			}
			if plan.Blocking || len(plan.Intents) != 0 || len(plan.Migrations) != 0 {
				t.Fatalf("inactive plan = %#v", plan)
			}
			prepared, err := inspection.PrepareWithPreservation(nil, nil, nil)
			if err != nil {
				t.Fatalf("PrepareWithPreservation() error = %v", err)
			}
			if len(prepared.Transitions()) != 0 {
				t.Fatalf("inactive transitions = %#v", prepared.Transitions())
			}
		})
	}
}

func assertDeselectionRelinquishes(
	t *testing.T,
	projection releasecontract.MCPProjection,
	entries map[domain.Location]hostfs.Entry,
) {
	t.Helper()
	inspection := inspectDeselectionCase(t, projection, entries)
	plan, err := inspection.PlanWithPreservation(nil, nil, nil)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if plan.Blocking || len(plan.Intents) != 1 ||
		plan.Intents[0].Kind != mcpconfiguration.IntentRelinquish {
		t.Fatalf("plan = %#v", plan)
	}
	prepared, err := inspection.PrepareWithPreservation(nil, nil, nil)
	if err != nil {
		t.Fatalf("PrepareWithPreservation() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 1 ||
		transitions[0].Mutations[0].Target != projection.RegistryTarget {
		t.Fatalf("relinquish transitions = %#v", transitions)
	}
}

func TestPreservedComponentEmitsNoIntentMigrationOrTransition(t *testing.T) {
	host := antigravityMigrationHost(antigravityDesired, antigravityDesired)
	inspection := inspectAntigravityPrepared(t, host)
	preserved := []domain.ComponentID{domain.ComponentAntigravity2}

	plan, err := inspection.PlanWithPreservation(nil, preserved, nil)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if len(plan.Intents) != 0 || len(plan.Migrations) != 0 || plan.Blocking {
		t.Fatalf("preserved plan = %#v", plan)
	}
	prepared, err := inspection.PrepareWithPreservation(nil, preserved, nil)
	if err != nil {
		t.Fatalf("PrepareWithPreservation() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("preserved transitions = %#v", prepared.Transitions())
	}
}

func TestInactiveAntigravityMaterialIntentIncludesMigrationAssessment(t *testing.T) {
	host := antigravityMigrationHost(antigravityDesired, antigravityDesired)
	inspection := inspectAntigravityPrepared(t, host)

	plan, err := inspection.PlanWithPreservation(nil, nil, nil)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if len(plan.Intents) != 1 || plan.Intents[0].Kind != mcpconfiguration.IntentRemove ||
		len(plan.Migrations) != 1 || !plan.Migrations[0].RequiresMigration {
		t.Fatalf("inactive Antigravity plan = %#v", plan)
	}
}

type deselectionCodecCase struct {
	name           string
	projection     releasecontract.MCPProjection
	ownedEntries   map[domain.Location]hostfs.Entry
	changedEntries map[domain.Location]hostfs.Entry
	deletedEntries map[domain.Location]hostfs.Entry
}

func deselectionCodecCases() []deselectionCodecCase {
	return []deselectionCodecCase{
		openCodeDeselectionCase(),
		claudeDeselectionCase(),
		codexDeselectionCase(),
		antigravityDeselectionCase(),
	}
}

func openCodeDeselectionCase() deselectionCodecCase {
	return deselectionCodecCase{
		name: "OpenCode", projection: projection(),
		ownedEntries: openCodePreparedHost(
			[]byte(`{"mcp":{"context7":`+desired+`}}`), []byte(owned(desired)),
		).entries,
		changedEntries: openCodePreparedHost(
			[]byte(`{"mcp":{"context7":{"type":"remote","url":"https://user.example/mcp"}}}`),
			[]byte(owned(desired)),
		).entries,
		deletedEntries: openCodePreparedHost(
			[]byte(`{"mcp":{}}`), []byte(owned(desired)),
		).entries,
	}
}

func claudeDeselectionCase() deselectionCodecCase {
	return deselectionCodecCase{
		name: "Claude Code", projection: claudeProjection(),
		ownedEntries: claudePreparedHost(
			[]byte(`{"mcpServers":{"context7":`+claudeDesired+`}}`),
			[]byte(claudeOwned(claudeDesired)),
		).entries,
		changedEntries: claudePreparedHost(
			[]byte(`{"mcpServers":{"context7":{"type":"http","url":"https://user.example/mcp"}}}`),
			[]byte(claudeOwned(claudeDesired)),
		).entries,
		deletedEntries: claudePreparedHost(
			[]byte(`{"mcpServers":{}}`), []byte(claudeOwned(claudeDesired)),
		).entries,
	}
}

func codexDeselectionCase() deselectionCodecCase {
	return deselectionCodecCase{
		name: "Codex", projection: codexProjection(),
		ownedEntries: codexPreparedHost(
			[]byte(codexManagedBlock("https://mcp.context7.com/mcp", "empty", "\n")),
			[]byte(codexManagedRegistry("https://mcp.context7.com/mcp")),
		).entries,
		changedEntries: codexPreparedHost(
			[]byte(codexManagedBlock("https://user.example/mcp", "empty", "\n")),
			[]byte(codexManagedRegistry("https://mcp.context7.com/mcp")),
		).entries,
		deletedEntries: codexPreparedHost(
			[]byte("model = \"gpt\"\n"),
			[]byte(codexManagedRegistry("https://mcp.context7.com/mcp")),
		).entries,
	}
}

func antigravityDeselectionCase() deselectionCodecCase {
	return deselectionCodecCase{
		name: "Antigravity", projection: antigravityProjection(),
		ownedEntries: antigravityPreparedHost(
			[]byte(`{"mcpServers":{"context7":`+antigravityDesired+`}}`),
			[]byte(antigravityOwned(antigravityDesired)),
		).entries,
		changedEntries: antigravityPreparedHost(
			[]byte(`{"mcpServers":{"context7":{"serverUrl":"https://user.example/mcp"}}}`),
			[]byte(antigravityOwned(antigravityDesired)),
		).entries,
		deletedEntries: antigravityPreparedHost(
			[]byte(`{"mcpServers":{}}`),
			[]byte(antigravityOwned(antigravityDesired)),
		).entries,
	}
}

func inspectDeselectionCase(
	t *testing.T,
	projection releasecontract.MCPProjection,
	entries map[domain.Location]hostfs.Entry,
) mcpconfiguration.Inspection {
	t.Helper()
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection}, catalog(t), &fakeHost{entries: entries},
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	return inspection
}
