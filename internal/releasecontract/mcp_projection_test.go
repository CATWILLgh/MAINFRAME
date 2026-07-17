package releasecontract_test

import (
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadDerivesOpenCodeMCPProjectionFromCatalog(t *testing.T) {
	root, _ := writeOpenCodeProjectionFixture(t)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	if len(release.MCPProjections) != 1 {
		t.Fatalf("MCP projections = %#v", release.MCPProjections)
	}
	projection := release.MCPProjections[0]
	if projection.ID != "opencode.mcp.context7" ||
		projection.ComponentID != domain.ComponentOpenCode ||
		projection.DesiredEntry != `{"type":"remote","url":"https://mcp.context7.com/mcp"}` {
		t.Fatalf("MCP projection = %#v", projection)
	}
}

func TestLoadDerivesClaudeMCPProjectionFromCatalog(t *testing.T) {
	root, _ := writeClaudeProjectionFixture(t)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	if len(release.MCPProjections) != 1 {
		t.Fatalf("MCP projections = %#v", release.MCPProjections)
	}
	projection := release.MCPProjections[0]
	if projection.ID != "claude-code.mcp.context7" ||
		projection.ComponentID != domain.ComponentClaudeCode ||
		projection.Target != (domain.Location{Root: domain.RootHome, Path: ".claude.json"}) ||
		projection.DesiredEntry != `{"type":"http","url":"https://mcp.context7.com/mcp"}` {
		t.Fatalf("MCP projection = %#v", projection)
	}
}

func TestLoadDerivesCodexMCPProjectionFromCatalog(t *testing.T) {
	root, _ := writeCodexProjectionFixture(t)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	if len(release.MCPProjections) != 1 {
		t.Fatalf("MCP projections = %#v", release.MCPProjections)
	}
	projection := release.MCPProjections[0]
	if projection.ID != "codex.mcp.context7" ||
		projection.ComponentID != domain.ComponentCodex ||
		projection.Target != (domain.Location{Root: domain.RootCodexConfig, Path: "config.toml"}) ||
		projection.DesiredEntry != `{"url":"https://mcp.context7.com/mcp"}` {
		t.Fatalf("MCP projection = %#v", projection)
	}
}

func TestLoadRejectsInvalidCodexMCPProjectionContract(t *testing.T) {
	tests := map[string]func(map[string]any){
		"OpenCode codec": func(record map[string]any) {
			record["codec"] = "opencode-remote-v1"
		},
		"foreign target root": func(record map[string]any) {
			record["target"].(map[string]any)["root"] = "home"
		},
		"wrong target path": func(record map[string]any) {
			record["target"].(map[string]any)["path"] = "settings.toml"
		},
		"wrong pointer": func(record map[string]any) {
			record["map_pointer"] = "/mcp"
		},
		"foreign registry": func(record map[string]any) {
			record["registry"].(map[string]any)["target"].(map[string]any)["root"] = "home"
		},
		"keyed profile": func(record map[string]any) {
			record["profile"] = "remote-api-key"
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root, manifestPath := writeCodexProjectionFixture(t)
			manifest := readObject(t, manifestPath)
			record := manifest["mcp_projections"].([]any)[0].(map[string]any)
			mutate(record)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid Codex MCP projection was accepted")
			}
		})
	}
}

func TestLoadRejectsMixedDocumentFormatsAtOneSemanticTarget(t *testing.T) {
	root, manifestPath := writeCodexProjectionFixture(t)
	manifest := readObject(t, manifestPath)
	configPath := filepath.Join(root, "bundles/codex/config.json")
	writeFile(t, configPath, `{"unrelated":true}`+"\n", 0o644)
	manifest["resources"] = []any{map[string]any{
		"id": "codex.config-json", "strategy": "json-key-merge",
		"source": "config.json",
		"target": map[string]any{"root": "codex-config", "path": "config.toml"},
		"observation": "supported", "apply": "unimplemented",
		"owned_json_pointers": []any{"/unrelated"},
	}}
	manifest["payload_files"] = []any{payloadRow(t, configPath, "config.json")}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil ||
		!strings.Contains(err.Error(), "format") {
		t.Fatalf("mixed document format error = %v", err)
	}
}

func TestLoadRejectsInvalidClaudeMCPProjectionContract(t *testing.T) {
	tests := map[string]func(map[string]any){
		"OpenCode codec": func(record map[string]any) {
			record["codec"] = "opencode-remote-v1"
		},
		"foreign target root": func(record map[string]any) {
			record["target"].(map[string]any)["root"] = "claude-config"
		},
		"foreign home path": func(record map[string]any) {
			record["target"].(map[string]any)["path"] = ".profile"
		},
		"wrong pointer": func(record map[string]any) {
			record["map_pointer"] = "/mcp"
		},
		"registry under home": func(record map[string]any) {
			record["registry"].(map[string]any)["target"].(map[string]any)["root"] = "home"
		},
		"wrong registry path": func(record map[string]any) {
			record["registry"].(map[string]any)["target"].(map[string]any)["path"] = "mainframe-mcp.json"
		},
		"keyed profile": func(record map[string]any) {
			record["profile"] = "remote-api-key"
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root, manifestPath := writeClaudeProjectionFixture(t)
			manifest := readObject(t, manifestPath)
			record := manifest["mcp_projections"].([]any)[0].(map[string]any)
			mutate(record)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid Claude MCP projection was accepted")
			}
		})
	}
}

func TestLoadRejectsInvalidMCPProjectionContract(t *testing.T) {
	tests := map[string]func(map[string]any){
		"unknown field":     func(record map[string]any) { record["unknown"] = true },
		"unsupported codec": func(record map[string]any) { record["codec"] = "unknown" },
		"foreign root": func(record map[string]any) {
			record["target"].(map[string]any)["root"] = "claude-config"
		},
		"wrong pointer":   func(record map[string]any) { record["map_pointer"] = "/permission" },
		"unknown profile": func(record map[string]any) { record["profile"] = "unknown" },
		"keyed profile":   func(record map[string]any) { record["profile"] = "remote-api-key" },
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root, manifestPath := writeOpenCodeProjectionFixture(t)
			manifest := readObject(t, manifestPath)
			record := manifest["mcp_projections"].([]any)[0].(map[string]any)
			mutate(record)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid MCP projection was accepted")
			}
		})
	}
}

func TestLoadRejectsUnsortedMCPProjections(t *testing.T) {
	root, manifestPath := writeOpenCodeProjectionFixture(t)
	manifest := readObject(t, manifestPath)
	second := validMCPProjectionRecord()
	second["id"] = "a.mcp.context7"
	second["server"] = "another"
	second["entry_key"] = "another"
	second["registry"].(map[string]any)["target"].(map[string]any)["path"] =
		"opencode.json.mainframe-mcp-a.json"
	manifest["mcp_projections"] = append(
		manifest["mcp_projections"].([]any), second,
	)
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil ||
		!strings.Contains(err.Error(), "sorted") {
		t.Fatalf("unsorted MCP projections error = %v", err)
	}
}

func TestLoadAllowsMCPProjectionsToShareOneRegistry(t *testing.T) {
	root, manifestPath := writeOpenCodeProjectionFixture(t)
	manifest := readObject(t, manifestPath)
	second := validMCPProjectionRecord()
	second["id"] = "opencode.mcp.docs"
	second["server"] = "docs"
	second["entry_key"] = "docs"
	manifest["mcp_projections"] = append(
		manifest["mcp_projections"].([]any), second,
	)
	writeJSON(t, manifestPath, manifest, 0o644)

	catalogPath := filepath.Join(root, "metadata/mcp-catalog.json")
	catalog := readObject(t, catalogPath)
	servers := catalog["servers"].([]any)
	payload, _ := json.Marshal(servers[0])
	var server map[string]any
	_ = json.Unmarshal(payload, &server)
	server["id"] = "docs"
	server["name"] = "Docs"
	catalog["servers"] = append(servers, server)
	writeJSON(t, catalogPath, catalog, 0o644)

	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	index["mcp_catalog"].(map[string]any)["sha256"] = digest(t, catalogPath)
	writeJSON(t, indexPath, index, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("shared MCP registry load error = %v", err)
	}
	if len(release.MCPProjections) != 2 {
		t.Fatalf("MCP projections = %#v", release.MCPProjections)
	}
}
