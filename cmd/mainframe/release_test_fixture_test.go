package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type planReleaseFixture struct {
	root     string
	payloads map[domain.ComponentID]string
}

type planReleaseComponent struct {
	id           domain.ComponentID
	dependencies []string
	root         domain.RootID
	target       string
}

func usePlanRelease(t *testing.T) planReleaseFixture {
	t.Helper()
	fixture := writePlanReleaseFixture(t)
	t.Setenv(releaseRootEnvironment, fixture.root)
	return fixture
}

func writePlanReleaseFixture(t *testing.T) planReleaseFixture {
	t.Helper()
	root := t.TempDir()
	components := []planReleaseComponent{
		{id: domain.ComponentAntigravity2, dependencies: []string{"credential-tools", "mainframe-cli"}, root: domain.RootAntigravityConfig, target: "AGENTS.md"},
		{id: domain.ComponentClaudeCode, dependencies: []string{"credential-tools", "mainframe-cli"}, root: domain.RootClaudeConfig, target: "CLAUDE.md"},
		{id: domain.ComponentCodex, dependencies: []string{"credential-tools", "mainframe-cli"}, root: domain.RootCodexConfig, target: "AGENTS.md"},
		{id: "credential-tools", dependencies: []string{}, root: domain.RootUserBin, target: "secret"},
		{id: "mainframe-cli", dependencies: []string{}, root: domain.RootUserBin, target: "mainframe"},
		{id: domain.ComponentOpenCode, dependencies: []string{"credential-tools", "mainframe-cli"}, root: domain.RootOpenCodeConfig, target: "AGENTS.md"},
	}
	entries := make([]map[string]any, 0, len(components))
	payloads := make(map[domain.ComponentID]string, len(components))
	for _, component := range components {
		entry, payload := writePlanBundle(t, root, component)
		entries = append(entries, entry)
		payloads[component.id] = payload
	}
	catalogPath := writePlanCatalog(t, root)
	writeFixtureJSON(t, filepath.Join(root, "release.json"), map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-release",
		"release_id":     "cli-plan-test",
		"mcp_catalog": map[string]any{
			"path": "metadata/mcp-catalog.json", "sha256": fixtureDigest(t, catalogPath),
		},
		"manifests": entries,
	}, 0o644)
	return planReleaseFixture{root: root, payloads: payloads}
}

func writePlanBundle(
	t *testing.T,
	releaseRoot string,
	component planReleaseComponent,
) (map[string]any, string) {
	t.Helper()
	bundleRoot := filepath.Join(releaseRoot, "bundles", string(component.id))
	if err := os.MkdirAll(bundleRoot, 0o755); err != nil {
		t.Fatalf("mkdir bundle: %v", err)
	}
	payloadPath := filepath.Join(bundleRoot, component.target)
	writeFixtureFile(t, payloadPath, []byte("release payload\n"), 0o644)
	manifestPath := filepath.Join(bundleRoot, "bundle.json")
	writeFixtureJSON(t, manifestPath, map[string]any{
		"schema_version":   2,
		"kind":             "mainframe-bundle",
		"component":        component.id,
		"dependencies":     component.dependencies,
		"install_units":    []any{map[string]any{"id": string(component.id) + ".artifact", "kind": "file", "source": component.target, "target": map[string]any{"root": component.root, "path": component.target}}},
		"legacy_artifacts": []any{},
		"resources":        []any{},
		"payload_files":    []any{fixturePayloadRow(t, payloadPath, component.target)},
		"runtime_profile":  map[string]string{},
		"mcp_projections":  []any{},
	}, 0o644)
	return map[string]any{
		"component": component.id,
		"path":      filepath.ToSlash(filepath.Join("bundles", string(component.id), "bundle.json")),
		"sha256":    fixtureDigest(t, manifestPath),
	}, payloadPath
}

func writePlanCatalog(t *testing.T, releaseRoot string) string {
	t.Helper()
	_, current, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve fixture source")
	}
	payload, err := os.ReadFile(filepath.Join(filepath.Dir(current), "..", "..", "internal", "mcpcatalog", "catalog.json"))
	if err != nil {
		t.Fatalf("read MCP catalog fixture: %v", err)
	}
	path := filepath.Join(releaseRoot, "metadata", "mcp-catalog.json")
	writeFixtureFile(t, path, payload, 0o644)
	return path
}

func fixturePayloadRow(t *testing.T, path, relative string) map[string]any {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat payload: %v", err)
	}
	return map[string]any{
		"path": relative, "mode": "0644", "size": info.Size(), "sha256": fixtureDigest(t, path),
	}
}

func writeFixtureJSON(t *testing.T, path string, value any, mode os.FileMode) {
	t.Helper()
	payload, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("encode fixture JSON: %v", err)
	}
	writeFixtureFile(t, path, append(payload, '\n'), mode)
}

func writeFixtureFile(t *testing.T, path string, payload []byte, mode os.FileMode) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir fixture parent: %v", err)
	}
	if err := os.WriteFile(path, payload, mode); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
}

func fixtureDigest(t *testing.T, path string) string {
	t.Helper()
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read fixture digest source: %v", err)
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}
