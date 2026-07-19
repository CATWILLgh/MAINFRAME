package mcpconfiguration_test

import (
	"io/fs"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPlanAssessesAntigravityMCPConfigurationLocations(t *testing.T) {
	for _, test := range antigravityMigrationCases() {
		t.Run(test.name, func(t *testing.T) {
			assertAntigravityMigration(t, test)
		})
	}
}

type antigravityMigrationCase struct {
	name           string
	canonical      string
	legacy         string
	wantState      mcpconfiguration.MigrationState
	wantMigration  bool
	wantConflict   bool
	wantAssessment bool
}

func antigravityMigrationCases() []antigravityMigrationCase {
	return []antigravityMigrationCase{
		{name: "neither"},
		{
			name: "legacy only", legacy: `{"mcpServers":{"context7":{"serverUrl":"https://legacy-secret.example/mcp"}}}`,
			wantState: mcpconfiguration.MigrationLegacyOnly, wantMigration: true,
			wantAssessment: true,
		},
		{
			name: "canonical only", canonical: `{"mcpServers":{}}`,
			wantState: mcpconfiguration.MigrationCanonicalOnly, wantAssessment: true,
		},
		{
			name:      "equivalent dual",
			canonical: `{"theme":"dark","mcpServers":{"context7":{"serverUrl":"https://example.invalid/mcp"}}}`,
			legacy:    "{\n  \"mcpServers\": {\"context7\": {\"serverUrl\": \"https://example.invalid/mcp\"}},\n  \"theme\": \"dark\"\n}",
			wantState: mcpconfiguration.MigrationEquivalentDual, wantMigration: true,
			wantAssessment: true,
		},
		{
			name:      "conflicting dual",
			canonical: `{"mcpServers":{"context7":{"serverUrl":"https://canonical-secret.example/mcp"}}}`,
			legacy:    `{"mcpServers":{"context7":{"serverUrl":"https://legacy-secret.example/mcp"}},"unknown":true}`,
			wantState: mcpconfiguration.MigrationConflictingDual, wantMigration: true,
			wantConflict: true, wantAssessment: true,
		},
		{
			name: "invalid legacy", canonical: `{"mcpServers":{}}`,
			legacy:    `{"mcpServers":{"private-header":"token-secret"}`,
			wantState: mcpconfiguration.MigrationInvalidLegacy, wantMigration: true,
			wantConflict: true, wantAssessment: true,
		},
		{
			name: "legacy root array", legacy: `[]`,
			wantState: mcpconfiguration.MigrationInvalidLegacy, wantMigration: true,
			wantConflict: true, wantAssessment: true,
		},
		{
			name: "legacy root null", legacy: `null`,
			wantState: mcpconfiguration.MigrationInvalidLegacy, wantMigration: true,
			wantConflict: true, wantAssessment: true,
		},
		{
			name: "legacy MCP array", legacy: `{"mcpServers":[]}`,
			wantState: mcpconfiguration.MigrationInvalidLegacy, wantMigration: true,
			wantConflict: true, wantAssessment: true,
		},
	}
}

func assertAntigravityMigration(t *testing.T, test antigravityMigrationCase) {
	t.Helper()
	host := antigravityLegacyHost(test.canonical, test.legacy)
	inspection := inspectAntigravityPrepared(t, host)
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentAntigravity2}, nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	if !test.wantAssessment {
		if len(plan.Migrations) != 0 {
			t.Fatalf("migrations = %#v", plan.Migrations)
		}
		return
	}
	if len(plan.Migrations) != 1 {
		t.Fatalf("migrations = %#v", plan.Migrations)
	}
	migration := plan.Migrations[0]
	if migration.ComponentID != domain.ComponentAntigravity2 ||
		migration.State != test.wantState ||
		migration.RequiresMigration != test.wantMigration ||
		migration.Conflict != test.wantConflict {
		t.Fatalf("migration = %#v", migration)
	}
	for _, secret := range []string{
		"legacy-secret", "canonical-secret", "private-header", "token-secret",
	} {
		if strings.Contains(migration.Reason, secret) {
			t.Fatalf("migration reason exposes %q: %q", secret, migration.Reason)
		}
	}
	if plan.Blocking {
		t.Fatalf("observational migration blocked a plan without material MCP intent: %#v", plan)
	}
}

func TestPlanTreatsUnsafeLegacyAntigravityFilesAsInvalid(t *testing.T) {
	tests := []struct {
		name  string
		entry hostfs.Entry
		err   error
	}{
		{name: "symbolic link", entry: hostfs.Entry{Kind: hostfs.EntrySymlink}},
		{name: "non regular", entry: hostfs.Entry{Kind: hostfs.EntryDirectory}},
		{name: "inspection failure", err: fs.ErrPermission},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := antigravityLegacyHost("", "")
			host.entries[antigravityLegacyLocation()] = test.entry
			if test.err != nil {
				delete(host.entries, antigravityLegacyLocation())
				host.failures = map[domain.Location]error{antigravityLegacyLocation(): test.err}
			}
			inspection := inspectAntigravityPrepared(t, host)
			plan, err := inspection.Plan([]domain.ComponentID{domain.ComponentAntigravity2}, nil)
			if err != nil {
				t.Fatal(err)
			}
			if len(plan.Migrations) != 1 ||
				plan.Migrations[0].State != mcpconfiguration.MigrationInvalidLegacy ||
				!plan.Migrations[0].Conflict || !plan.Migrations[0].RequiresMigration {
				t.Fatalf("migrations = %#v", plan.Migrations)
			}
		})
	}
}

func TestPlanOmitsAntigravityMigrationWhenComponentIsNotSelected(t *testing.T) {
	host := antigravityLegacyHost("", `{"mcpServers":{}}`)
	inspection := inspectAntigravityPrepared(t, host)
	plan, err := inspection.Plan([]domain.ComponentID{domain.ComponentCodex}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(plan.Migrations) != 0 {
		t.Fatalf("migrations = %#v", plan.Migrations)
	}
}

func TestAntigravityLegacyInspectionIsImmutableAndReadsEachLocationOnce(t *testing.T) {
	host := antigravityLegacyHost("", `{"mcpServers":{}}`)
	inspection := inspectAntigravityPrepared(t, host)
	readsAfterInspection := host.reads
	host.entries[antigravityLegacyLocation()] = hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: []byte(`{"changed":true}`),
	}

	first, err := inspection.Plan([]domain.ComponentID{domain.ComponentAntigravity2}, nil)
	if err != nil {
		t.Fatal(err)
	}
	second, err := inspection.Plan([]domain.ComponentID{domain.ComponentAntigravity2}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(first.Migrations) != 1 || first.Migrations[0].State != mcpconfiguration.MigrationLegacyOnly ||
		len(second.Migrations) != 1 || second.Migrations[0] != first.Migrations[0] {
		t.Fatalf("immutable plans = %#v then %#v", first, second)
	}
	if host.reads != readsAfterInspection || readsAfterInspection != 3 {
		t.Fatalf("host reads = %d after inspection, then %d", readsAfterInspection, host.reads)
	}
}

func TestPrepareGatesOnlyMaterialAntigravityMCPChanges(t *testing.T) {
	host := antigravityLegacyHost("", `{"mcpServers":{}}`)
	inspection := inspectAntigravityPrepared(t, host)

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, nil,
	)
	if err != nil {
		t.Fatalf("Prepare() without MCP selection error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("transitions = %#v", prepared.Transitions())
	}

	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentAntigravity2}, antigravitySelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if plan.Blocking {
		t.Fatalf("non-conflicting migration should be gated during preparation: %#v", plan)
	}
	if _, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, antigravitySelection(),
	); err == nil || !strings.Contains(err.Error(), "migration") {
		t.Fatalf("Prepare() error = %v", err)
	}
}

func TestConflictingAntigravityLocationsBlockMaterialMCPPlan(t *testing.T) {
	host := antigravityLegacyHost(
		`{"mcpServers":{}}`, `{"mcpServers":{"other":{"serverUrl":"https://example.invalid"}}}`,
	)
	inspection := inspectAntigravityPrepared(t, host)
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentAntigravity2}, antigravitySelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Blocking || len(plan.Migrations) != 1 || !plan.Migrations[0].Conflict {
		t.Fatalf("plan = %#v", plan)
	}
}

func TestAntigravityMigrationGateCoversAddUpdateAndRemove(t *testing.T) {
	old := `{"serverUrl":"https://old.example/mcp"}`
	tests := []struct {
		name       string
		host       *fakeHost
		selections []mcpcatalog.Selection
		want       mcpconfiguration.IntentKind
	}{
		{name: "add", host: antigravityLegacyHost("", `{"mcpServers":{}}`),
			selections: antigravitySelection(), want: mcpconfiguration.IntentAdd},
		{name: "update", host: antigravityMigrationHost(old, old),
			selections: antigravitySelection(), want: mcpconfiguration.IntentUpdate},
		{name: "remove", host: antigravityMigrationHost(antigravityDesired, antigravityDesired),
			want: mcpconfiguration.IntentRemove},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			inspection := inspectAntigravityPrepared(t, test.host)
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentAntigravity2}, test.selections,
			)
			if err != nil || len(plan.Intents) != 1 || plan.Intents[0].Kind != test.want {
				t.Fatalf("Plan() = %#v, %v", plan, err)
			}
			if _, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentAntigravity2}, test.selections,
			); err == nil || !strings.Contains(err.Error(), "migration") {
				t.Fatalf("Prepare() error = %v", err)
			}
		})
	}
}

func TestAntigravityLegacyStateDoesNotGateCodexMaterialIntent(t *testing.T) {
	host := antigravityLegacyHost("", `{"mcpServers":{}}`)
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{antigravityProjection(), codexProjection()},
		catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2, domain.ComponentCodex},
		codexSelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	if transitions := prepared.Transitions(); len(transitions) != 1 ||
		transitions[0].ResourceIDs[0] != "codex.mcp.context7" {
		t.Fatalf("transitions = %#v", transitions)
	}
}

func TestInactiveAntigravityMigrationScopeIgnoresUnrelatedMaterialIntent(t *testing.T) {
	host := antigravityLegacyHost("", `{"mcpServers":{}}`)
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{antigravityProjection(), codexProjection()},
		catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(plan.Migrations) != 0 || len(plan.Intents) != 1 ||
		plan.Intents[0].ComponentID != domain.ComponentCodex ||
		plan.Intents[0].Kind != mcpconfiguration.IntentAdd {
		t.Fatalf("isolated migration scope plan = %#v", plan)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	if transitions := prepared.Transitions(); len(transitions) != 1 ||
		transitions[0].ResourceIDs[0] != "codex.mcp.context7" {
		t.Fatalf("transitions = %#v", transitions)
	}
}

func antigravityLegacyHost(canonical, legacy string) *fakeHost {
	host := antigravityPreparedHost(byteOrNil(canonical), nil)
	if legacy != "" {
		host.entries[antigravityLegacyLocation()] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: []byte(legacy),
			Mode: 0o600, Device: 11, Inode: 403,
		}
	}
	return host
}

func antigravityMigrationHost(configEntry, registryEntry string) *fakeHost {
	config := `{"mcpServers":{"context7":` + configEntry + `}}`
	host := antigravityPreparedHost([]byte(config), []byte(antigravityOwned(registryEntry)))
	host.entries[antigravityLegacyLocation()] = hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: []byte(config),
		Mode: 0o600, Device: 11, Inode: 403,
	}
	return host
}

func antigravityLegacyLocation() domain.Location {
	return domain.Location{Root: domain.RootAntigravityData, Path: "mcp_config.json"}
}

func byteOrNil(value string) []byte {
	if value == "" {
		return nil
	}
	return []byte(value)
}
