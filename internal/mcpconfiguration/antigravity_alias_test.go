package mcpconfiguration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestPlanTreatsExactAntigravityCompatibilityAliasAsCanonicalOnly(t *testing.T) {
	host := antigravityLegacyHost(`{"mcpServers":{}}`, "")
	addAntigravityCompatibilityAlias(host)
	canonical := host.entries[antigravityCanonicalLocation()]

	inspection := inspectAntigravityPrepared(t, host)
	plan, err := inspection.Plan(
		[]domain.ComponentID{domain.ComponentAntigravity2},
		antigravitySelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(plan.Migrations) != 1 ||
		plan.Migrations[0].State != mcpconfiguration.MigrationCanonicalOnly ||
		plan.Migrations[0].RequiresMigration ||
		plan.Migrations[0].Conflict ||
		plan.Blocking {
		t.Fatalf("plan = %#v", plan)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2},
		antigravitySelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	preconditions := prepared.Preconditions()
	if len(preconditions) != 1 ||
		preconditions[0].Kind != configuration.ReadPreconditionSymlink ||
		preconditions[0].Target != antigravityLegacyLocation() ||
		preconditions[0].Device != 11 ||
		preconditions[0].Inode != 404 ||
		preconditions[0].ExpectedTargetPath != canonical.Path {
		t.Fatalf("preconditions = %#v", preconditions)
	}
}

func TestAntigravityCompatibilityAliasNeedsNoPreconditionWithoutMaterialIntent(t *testing.T) {
	host := antigravityPreparedHost([]byte(`{"mcpServers":{}}`), nil)
	addAntigravityCompatibilityAlias(host)
	inspection := inspectAntigravityPrepared(t, host)

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentAntigravity2}, nil,
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 || len(prepared.Preconditions()) != 0 {
		t.Fatalf(
			"prepared = transitions %#v, preconditions %#v",
			prepared.Transitions(),
			prepared.Preconditions(),
		)
	}
}

func TestAntigravityCompatibilityAliasRequiresCanonicalRegularFile(t *testing.T) {
	tests := []struct {
		name      string
		canonical hostfs.Entry
	}{
		{name: "missing"},
		{
			name: "canonical symbolic link",
			canonical: hostfs.Entry{
				Kind:              hostfs.EntrySymlink,
				Path:              "/home/test/.gemini/config/mcp_config.json",
				SymlinkTargetPath: "/home/test/foreign/mcp_config.json",
			},
		},
		{
			name: "canonical directory",
			canonical: hostfs.Entry{
				Kind: hostfs.EntryDirectory,
				Path: "/home/test/.gemini/config/mcp_config.json",
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := antigravityLegacyHost("", "")
			if test.canonical.Kind != "" {
				host.entries[antigravityCanonicalLocation()] = test.canonical
			}
			host.entries[antigravityLegacyLocation()] = hostfs.Entry{
				Kind:              hostfs.EntrySymlink,
				Path:              "/home/test/.gemini/antigravity/mcp_config.json",
				SymlinkTargetPath: "/home/test/.gemini/config/mcp_config.json",
			}
			inspection := inspectAntigravityPrepared(t, host)
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentAntigravity2}, nil,
			)
			if err != nil {
				t.Fatal(err)
			}
			if len(plan.Migrations) != 1 ||
				plan.Migrations[0].State != mcpconfiguration.MigrationInvalidLegacy ||
				!plan.Migrations[0].RequiresMigration ||
				!plan.Migrations[0].Conflict {
				t.Fatalf("migrations = %#v", plan.Migrations)
			}
		})
	}
}

func TestAntigravityCompatibilityAliasAllowsAddUpdateAndRemove(t *testing.T) {
	old := `{"serverUrl":"https://old.example/mcp"}`
	tests := []struct {
		name       string
		host       *fakeHost
		selections []mcpcatalog.Selection
		want       mcpconfiguration.IntentKind
	}{
		{
			name:       "add",
			host:       antigravityPreparedHost([]byte(`{"mcpServers":{}}`), nil),
			selections: antigravitySelection(),
			want:       mcpconfiguration.IntentAdd,
		},
		{
			name: "update",
			host: antigravityPreparedHost(
				[]byte(`{"mcpServers":{"context7":`+old+`}}`),
				[]byte(antigravityOwned(old)),
			),
			selections: antigravitySelection(),
			want:       mcpconfiguration.IntentUpdate,
		},
		{
			name: "remove",
			host: antigravityPreparedHost(
				[]byte(`{"mcpServers":{"context7":`+antigravityDesired+`}}`),
				[]byte(antigravityOwned(antigravityDesired)),
			),
			want: mcpconfiguration.IntentRemove,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			addAntigravityCompatibilityAlias(test.host)
			inspection := inspectAntigravityPrepared(t, test.host)
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentAntigravity2}, test.selections,
			)
			if err != nil || plan.Blocking ||
				len(plan.Migrations) != 1 ||
				plan.Migrations[0].State != mcpconfiguration.MigrationCanonicalOnly ||
				len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != test.want {
				t.Fatalf("Plan() = %#v, %v", plan, err)
			}
			prepared, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentAntigravity2}, test.selections,
			)
			if err != nil {
				t.Fatalf("Prepare() error = %v", err)
			}
			if len(prepared.Preconditions()) != 1 {
				t.Fatalf("preconditions = %#v", prepared.Preconditions())
			}
		})
	}
}

func addAntigravityCompatibilityAlias(host *fakeHost) {
	canonical := host.entries[antigravityCanonicalLocation()]
	canonical.Path = "/home/test/.gemini/config/mcp_config.json"
	host.entries[antigravityCanonicalLocation()] = canonical
	host.entries[antigravityLegacyLocation()] = hostfs.Entry{
		Kind:              hostfs.EntrySymlink,
		Path:              "/home/test/.gemini/antigravity/mcp_config.json",
		SymlinkTargetPath: canonical.Path,
		Mode:              0o777,
		Device:            11,
		Inode:             404,
	}
}
