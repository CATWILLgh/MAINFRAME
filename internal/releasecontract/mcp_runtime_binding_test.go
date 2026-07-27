package releasecontract_test

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const keyedOpenCodeDesired = `{"headers":{"CONTEXT7_API_KEY":"{env:CUSTOM_CONTEXT7_KEY}"},"type":"remote","url":"https://mcp.context7.com/mcp"}`

func TestBindMCPProjectionProfileDerivesKeyedOpenCodeEntryWithoutReadingSecret(t *testing.T) {
	t.Setenv("CUSTOM_CONTEXT7_KEY", "raw-secret-must-not-appear")
	projection := loadOpenCodeProjection(t)

	bound, err := releasecontract.BindMCPProjectionProfile(
		projection, runtimeBindingCatalog(t), "remote-api-key", "CUSTOM_CONTEXT7_KEY",
	)
	if err != nil {
		t.Fatalf("BindMCPProjectionProfile() error = %v", err)
	}
	if bound.ID != projection.ID ||
		bound.Target != projection.Target ||
		bound.RegistryTarget != projection.RegistryTarget ||
		bound.ProfileID != "remote-api-key" ||
		bound.DesiredEntry != keyedOpenCodeDesired {
		t.Fatalf("bound projection = %#v", bound)
	}
	if strings.Contains(bound.DesiredEntry, "raw-secret-must-not-appear") {
		t.Fatalf("bound desired entry contains raw secret: %s", bound.DesiredEntry)
	}
}

func TestBindMCPProjectionProfileFailsClosedForUnsafeBindings(t *testing.T) {
	tests := []struct {
		name        string
		projection  func(*testing.T) releasecontract.MCPProjection
		environment string
	}{
		{
			name: "invalid environment variable", projection: loadOpenCodeProjection,
			environment: "CUSTOM-CONTEXT7-KEY",
		},
		{
			name: "Claude keyed binding", projection: loadClaudeProjection,
			environment: "CUSTOM_CONTEXT7_KEY",
		},
		{
			name: "Codex keyed binding", projection: loadCodexProjection,
			environment: "CUSTOM_CONTEXT7_KEY",
		},
		{
			name: "Antigravity keyed binding", projection: loadAntigravityProjection,
			environment: "CUSTOM_CONTEXT7_KEY",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := releasecontract.BindMCPProjectionProfile(
				test.projection(t), runtimeBindingCatalog(t),
				"remote-api-key", test.environment,
			)
			if err == nil {
				t.Fatal("unsafe keyed binding was accepted")
			}
		})
	}
}

func loadOpenCodeProjection(t *testing.T) releasecontract.MCPProjection {
	t.Helper()
	root, _ := writeOpenCodeProjectionFixture(t)
	return loadOnlyProjection(t, root)
}

func loadClaudeProjection(t *testing.T) releasecontract.MCPProjection {
	t.Helper()
	root, _ := writeClaudeProjectionFixture(t)
	return loadOnlyProjection(t, root)
}

func loadCodexProjection(t *testing.T) releasecontract.MCPProjection {
	t.Helper()
	root, _ := writeCodexProjectionFixture(t)
	return loadOnlyProjection(t, root)
}

func loadAntigravityProjection(t *testing.T) releasecontract.MCPProjection {
	t.Helper()
	root, _ := writeAntigravityProjectionFixture(t)
	return loadOnlyProjection(t, root)
}

func loadOnlyProjection(t *testing.T, root string) releasecontract.MCPProjection {
	t.Helper()
	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if len(release.MCPProjections) != 1 {
		t.Fatalf("MCP projections = %#v", release.MCPProjections)
	}
	return release.MCPProjections[0]
}

func runtimeBindingCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	return catalog
}
