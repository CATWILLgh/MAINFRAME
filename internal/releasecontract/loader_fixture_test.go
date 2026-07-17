package releasecontract_test

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func writeFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	bundle := filepath.Join(root, "bundles/codex")
	if err := os.MkdirAll(bundle, 0o755); err != nil {
		t.Fatalf("mkdir bundle: %v", err)
	}
	writeFile(t, filepath.Join(bundle, "payload.txt"), "payload\n", 0o644)
	writeFile(t, filepath.Join(bundle, "config.json"), "{}\n", 0o644)
	manifest := map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-bundle",
		"component":      "codex",
		"dependencies":   []string{},
		"install_units": []any{map[string]any{
			"id":                     "codex.payload",
			"kind":                   "file",
			"source":                 "payload.txt",
			"target":                 map[string]any{"root": "codex-config", "path": "payload.txt"},
			"legacy_source_suffixes": []string{"dist/codex/payload.txt"},
		}},
		"legacy_artifacts": []any{map[string]any{
			"target":          map[string]any{"root": "codex-config", "path": "obsolete.txt"},
			"target_suffixes": []string{"export/obsolete.txt"},
		}},
		"resources": []any{map[string]any{
			"id":                     "codex.configuration",
			"strategy":               "json-key-merge",
			"source":                 "config.json",
			"target":                 map[string]any{"root": "codex-config", "path": "config.json"},
			"legacy_source_suffixes": []string{"dist/codex/config.json"},
			"observation":            "unimplemented",
			"apply":                  "unimplemented",
		}},
		"payload_files": []any{
			payloadRow(t, filepath.Join(bundle, "config.json"), "config.json"),
			payloadRow(t, filepath.Join(bundle, "payload.txt"), "payload.txt"),
		},
		"runtime_profile": map[string]string{"config_root": "${CODEX_HOME}"},
		"mcp_projections": []any{},
	}
	manifestPath := filepath.Join(bundle, "bundle.json")
	writeJSON(t, manifestPath, manifest, 0o644)
	if err := os.MkdirAll(filepath.Join(root, "metadata"), 0o755); err != nil {
		t.Fatalf("mkdir metadata: %v", err)
	}
	catalogPath := filepath.Join(root, "metadata/mcp-catalog.json")
	writeFile(t, catalogPath, catalogFixtureJSON(), 0o644)
	index := map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-release",
		"release_id":     "test-release",
		"mcp_catalog": map[string]any{
			"path":   "metadata/mcp-catalog.json",
			"sha256": digest(t, catalogPath),
		},
		"manifests": []any{map[string]any{
			"component": "codex",
			"path":      "bundles/codex/bundle.json",
			"sha256":    digest(t, manifestPath),
		}},
	}
	writeJSON(t, filepath.Join(root, "release.json"), index, 0o644)
	return root
}

func catalogFixtureJSON() string {
	return `{
  "schema_version": 1,
  "kind": "mainframe-mcp-catalog",
  "servers": [{
    "id": "context7",
    "name": "Context7",
    "summary": "Current library documentation for coding agents.",
    "publisher": "Upstash",
    "homepage_url": "https://context7.com",
    "documentation_url": "https://context7.com/docs/resources/all-clients",
    "repository": {"owner": "upstash", "name": "context7", "url": "https://github.com/upstash/context7"},
    "license": "MIT",
    "profiles": [{
      "id": "remote-keyless",
      "name": "Remote without API key",
      "transport": "streamable-http",
      "endpoint": "https://mcp.context7.com/mcp",
      "authentication": {"kind": "none", "placement": "none", "environment_variable": ""},
      "compatibility": [
        {"adapter": "antigravity-2", "status": "supported", "reason": ""},
        {"adapter": "claude-code", "status": "supported", "reason": ""},
        {"adapter": "codex", "status": "supported", "reason": ""},
        {"adapter": "opencode", "status": "supported", "reason": ""}
      ],
      "evidence": {"url": "https://github.com/upstash/context7#installation", "verified_on": "2026-07-17"}
    }]
  }]
}`
}

func validMCPProjectionRecord() map[string]any {
	return map[string]any{
		"id":          "opencode.mcp.context7",
		"codec":       "opencode-remote-v1",
		"server":      "context7",
		"profile":     "remote-keyless",
		"target":      map[string]any{"root": "opencode-config", "path": "opencode.json"},
		"map_pointer": "/mcp",
		"entry_key":   "context7",
		"registry": map[string]any{
			"target":          map[string]any{"root": "opencode-config", "path": "opencode.json.mainframe-mcp.json"},
			"schema_version":  1,
			"entries_pointer": "/servers",
		},
	}
}

func validClaudeMCPProjectionRecord() map[string]any {
	return map[string]any{
		"id":          "claude-code.mcp.context7",
		"codec":       "claude-user-http-v1",
		"server":      "context7",
		"profile":     "remote-keyless",
		"target":      map[string]any{"root": "home", "path": ".claude.json"},
		"map_pointer": "/mcpServers",
		"entry_key":   "context7",
		"registry": map[string]any{
			"target": map[string]any{
				"root": "claude-config", "path": "mainframe/mcp-ownership.json",
			},
			"schema_version":  1,
			"entries_pointer": "/servers",
		},
	}
}

func validCodexMCPProjectionRecord() map[string]any {
	return map[string]any{
		"id":          "codex.mcp.context7",
		"codec":       "codex-user-http-v1",
		"server":      "context7",
		"profile":     "remote-keyless",
		"target":      map[string]any{"root": "codex-config", "path": "config.toml"},
		"map_pointer": "/mcp_servers",
		"entry_key":   "context7",
		"registry": map[string]any{
			"target": map[string]any{
				"root": "codex-config", "path": "mainframe/mcp-ownership.json",
			},
			"schema_version":  1,
			"entries_pointer": "/servers",
		},
	}
}

func writeOpenCodeProjectionFixture(t *testing.T) (string, string) {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	for _, name := range []string{"config.json", "payload.txt"} {
		if err := os.Remove(filepath.Join(filepath.Dir(manifestPath), name)); err != nil {
			t.Fatalf("remove fixture payload: %v", err)
		}
	}
	manifest := readObject(t, manifestPath)
	manifest["component"] = "opencode"
	manifest["runtime_profile"] = map[string]string{
		"config_root": "${XDG_CONFIG_HOME}/opencode",
	}
	manifest["install_units"] = []any{}
	manifest["legacy_artifacts"] = []any{}
	manifest["resources"] = []any{}
	manifest["payload_files"] = []any{}
	manifest["mcp_projections"] = []any{validMCPProjectionRecord()}
	writeJSON(t, manifestPath, manifest, 0o644)
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	entry := index["manifests"].([]any)[0].(map[string]any)
	entry["component"] = "opencode"
	entry["sha256"] = digest(t, manifestPath)
	writeJSON(t, indexPath, index, 0o644)
	return root, manifestPath
}

func writeClaudeProjectionFixture(t *testing.T) (string, string) {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	for _, name := range []string{"config.json", "payload.txt"} {
		if err := os.Remove(filepath.Join(filepath.Dir(manifestPath), name)); err != nil {
			t.Fatalf("remove fixture payload: %v", err)
		}
	}
	manifest := readObject(t, manifestPath)
	manifest["component"] = "claude-code"
	manifest["runtime_profile"] = map[string]string{"config_root": "~/.claude"}
	manifest["install_units"] = []any{}
	manifest["legacy_artifacts"] = []any{}
	manifest["resources"] = []any{}
	manifest["payload_files"] = []any{}
	manifest["mcp_projections"] = []any{validClaudeMCPProjectionRecord()}
	writeJSON(t, manifestPath, manifest, 0o644)
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	entry := index["manifests"].([]any)[0].(map[string]any)
	entry["component"] = "claude-code"
	entry["sha256"] = digest(t, manifestPath)
	writeJSON(t, indexPath, index, 0o644)
	return root, manifestPath
}

func writeCodexProjectionFixture(t *testing.T) (string, string) {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	for _, name := range []string{"config.json", "payload.txt"} {
		if err := os.Remove(filepath.Join(filepath.Dir(manifestPath), name)); err != nil {
			t.Fatalf("remove fixture payload: %v", err)
		}
	}
	manifest := readObject(t, manifestPath)
	manifest["install_units"] = []any{}
	manifest["legacy_artifacts"] = []any{}
	manifest["resources"] = []any{}
	manifest["payload_files"] = []any{}
	manifest["mcp_projections"] = []any{validCodexMCPProjectionRecord()}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	return root, manifestPath
}

func payloadRow(t *testing.T, file, path string) map[string]any {
	t.Helper()
	info, err := os.Stat(file)
	if err != nil {
		t.Fatalf("stat payload: %v", err)
	}
	return map[string]any{
		"path":   path,
		"mode":   "0644",
		"size":   info.Size(),
		"sha256": digest(t, file),
	}
}

func rewriteIndexDigest(t *testing.T, root, manifestPath string) {
	t.Helper()
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	entries := index["manifests"].([]any)
	entries[0].(map[string]any)["sha256"] = digest(t, manifestPath)
	writeJSON(t, indexPath, index, 0o644)
}

func readObject(t *testing.T, path string) map[string]any {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	var value map[string]any
	if err := json.Unmarshal(data, &value); err != nil {
		t.Fatalf("decode %s: %v", path, err)
	}
	return value
}

func writeJSON(t *testing.T, path string, value any, mode os.FileMode) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("encode %s: %v", path, err)
	}
	writeFile(t, path, string(data)+"\n", mode)
}

func writeFile(t *testing.T, path, value string, mode os.FileMode) {
	t.Helper()
	if err := os.WriteFile(path, []byte(value), mode); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func appendFile(t *testing.T, path, value string) {
	t.Helper()
	file, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0)
	if err != nil {
		t.Fatalf("open %s: %v", path, err)
	}
	defer file.Close()
	if _, err := file.WriteString(value); err != nil {
		t.Fatalf("append %s: %v", path, err)
	}
}

func digest(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read digest source: %v", err)
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func location(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootCodexConfig, Path: path}
}
