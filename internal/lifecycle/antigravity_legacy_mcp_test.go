package lifecycle

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestAntigravityLegacyMCPAssessmentSurvivesLifecycleWithoutBlockingUnrelatedPreparation(
	t *testing.T,
) {
	service := antigravityLegacyLifecycleService(t)
	request := PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentAntigravity2},
	}
	preview, err := service.Preview(request)
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	assertLegacyMigrationIsPrivate(t, preview.MCP.Migrations)

	prepared, err := service.PrepareConfiguration(request)
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	if transitions := prepared.Transitions(); len(transitions) != 0 {
		t.Fatalf("unrelated preparation produced transitions: %#v", transitions)
	}
}

func antigravityLegacyLifecycleService(t *testing.T) Service {
	t.Helper()
	legacyPayload := []byte(`{
		"mcpServers": {
			"private-server": {
				"serverUrl": "https://private.example/mcp",
				"headers": {"Authorization": "private-token"}
			}
		}
	}`)
	host := lifecyclePreparationHost{
		{
			Root: domain.RootAntigravityData,
			Path: "mcp_config.json",
		}: {
			Kind: hostfs.EntryRegular, Content: legacyPayload, Mode: 0o600,
		},
	}
	configurationInspection, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{lifecycleAntigravityProjection()},
		lifecycleMCPCatalog(t),
		host,
	)
	if err != nil {
		t.Fatal(err)
	}
	service, err := NewWithInspections(
		testModel(t), domain.ObservedState{}, configurationInspection, mcpInspection,
	)
	if err != nil {
		t.Fatal(err)
	}
	return service
}

func assertLegacyMigrationIsPrivate(
	t *testing.T,
	migrations []mcpconfiguration.MigrationAssessment,
) {
	t.Helper()
	if len(migrations) != 1 {
		t.Fatalf("MCP migrations = %#v", migrations)
	}
	migration := migrations[0]
	if migration.ComponentID != domain.ComponentAntigravity2 ||
		migration.State != mcpconfiguration.MigrationLegacyOnly ||
		!migration.RequiresMigration || migration.Conflict {
		t.Fatalf("MCP migration = %#v", migration)
	}
	for _, private := range []string{
		"private-server", "private.example", "Authorization", "private-token",
	} {
		if strings.Contains(migration.Reason, private) {
			t.Fatalf("migration reason exposes %q: %q", private, migration.Reason)
		}
	}
}
