package releasecontract_test

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadBuildsInstallModelAndSeparateResourceInventory(t *testing.T) {
	root := writeFixture(t)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}

	if release.ID != "test-release" {
		t.Fatalf("release ID = %q", release.ID)
	}
	wantIndexSHA256 := digest(t, filepath.Join(root, "release.json"))
	if release.IndexSHA256 != wantIndexSHA256 {
		t.Fatalf("index digest = %q, want %q", release.IndexSHA256, wantIndexSHA256)
	}
	artifacts := release.Model.Artifacts()
	if len(artifacts) != 2 {
		t.Fatalf("artifact count = %d, want 2", len(artifacts))
	}
	desired, legacy := artifacts[0], artifacts[1]
	if desired.LegacyOnly {
		desired, legacy = legacy, desired
	}
	if desired.ComponentID != domain.ComponentCodex || desired.Target != location("payload.txt") {
		t.Fatalf("desired artifact = %#v", desired)
	}
	if desired.SourcePath != "bundles/codex/payload.txt" {
		t.Fatalf("desired source = %q", desired.SourcePath)
	}
	if !reflect.DeepEqual(desired.LegacyTargetSuffixes, []domain.ArtifactPath{"dist/codex/payload.txt"}) {
		t.Fatalf("desired legacy suffixes = %v", desired.LegacyTargetSuffixes)
	}
	if !legacy.LegacyOnly || legacy.Target != location("obsolete.txt") {
		t.Fatalf("legacy artifact = %#v", legacy)
	}
	if len(release.Resources) != 1 {
		t.Fatalf("resource count = %d", len(release.Resources))
	}
	resource := release.Resources[0]
	if resource.ID != "codex.configuration" || resource.ComponentID != domain.ComponentCodex {
		t.Fatalf("resource = %#v", resource)
	}
	if resource.SourcePath != "bundles/codex/config.json" || resource.Strategy != releasecontract.StrategyJSONKeyMerge {
		t.Fatalf("resource source/strategy = %#v", resource)
	}
	if !reflect.DeepEqual(resource.LegacySourceSuffixes, []domain.ArtifactPath{"dist/codex/config.json"}) {
		t.Fatalf("resource legacy sources = %v", resource.LegacySourceSuffixes)
	}
	if resource.Observation != releasecontract.SupportUnimplemented || resource.Apply != releasecontract.SupportUnimplemented {
		t.Fatalf("resource support = %#v", resource)
	}
	server, exists := release.MCPCatalog.Server("context7")
	if !exists || server.Name != "Context7" {
		t.Fatalf("MCP catalog server = %#v, exists = %t", server, exists)
	}
}

func TestLoadRejectsManifestAndPayloadTampering(t *testing.T) {
	t.Run("manifest digest", func(t *testing.T) {
		root := writeFixture(t)
		path := filepath.Join(root, "bundles/codex/bundle.json")
		appendFile(t, path, "\n")
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("tampered manifest was accepted")
		}
	})

	t.Run("payload digest", func(t *testing.T) {
		root := writeFixture(t)
		path := filepath.Join(root, "bundles/codex/payload.txt")
		if err := os.WriteFile(path, []byte("tampered\n"), 0o644); err != nil {
			t.Fatalf("tamper payload: %v", err)
		}
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("tampered payload was accepted")
		}
	})
}

func TestLoadRejectsCatalogTamperingAndOversizedCatalog(t *testing.T) {
	t.Run("digest", func(t *testing.T) {
		root := writeFixture(t)
		appendFile(t, filepath.Join(root, "metadata/mcp-catalog.json"), "\n")
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("tampered catalog was accepted")
		}
	})

	t.Run("size", func(t *testing.T) {
		root := writeFixture(t)
		catalogPath := filepath.Join(root, "metadata/mcp-catalog.json")
		writeFile(t, catalogPath, strings.Repeat(" ", (1<<20)+1), 0o644)
		indexPath := filepath.Join(root, "release.json")
		index := readObject(t, indexPath)
		index["mcp_catalog"].(map[string]any)["sha256"] = digest(t, catalogPath)
		writeJSON(t, indexPath, index, 0o644)
		_, err := releasecontract.Load(root)
		if err == nil || !strings.Contains(err.Error(), "exceeds") {
			t.Fatalf("oversized catalog error = %v", err)
		}
	})
}

func TestLoadRejectsCatalogOutsideReservedMetadataPath(t *testing.T) {
	root := writeFixture(t)
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	payloadPath := filepath.Join(root, "bundles/codex/payload.txt")
	index["mcp_catalog"] = map[string]any{
		"path": "bundles/codex/payload.txt", "sha256": digest(t, payloadPath),
	}
	writeJSON(t, indexPath, index, 0o644)
	_, err := releasecontract.Load(root)
	if err == nil || !strings.Contains(err.Error(), "reserved") {
		t.Fatalf("catalog ownership error = %v", err)
	}
}

func TestLoadRejectsUnknownAndDuplicateJSONFields(t *testing.T) {
	t.Run("unknown", func(t *testing.T) {
		root := writeFixture(t)
		index := filepath.Join(root, "release.json")
		payload := readObject(t, index)
		payload["unknown"] = true
		writeJSON(t, index, payload, 0o644)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("unknown release field was accepted")
		}
	})

	t.Run("duplicate", func(t *testing.T) {
		root := t.TempDir()
		raw := `{"schema_version":2,"schema_version":2,"kind":"mainframe-release","release_id":"test-release","manifests":[]}`
		if err := os.WriteFile(filepath.Join(root, "release.json"), []byte(raw), 0o644); err != nil {
			t.Fatalf("write index: %v", err)
		}
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("duplicate JSON key was accepted")
		}
	})

	for name, replacement := range map[string][]byte{
		"invalid UTF-8": {0xff},
		"surrogate":     []byte(`\uD800`),
	} {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			payload, err := os.ReadFile(manifestPath)
			if err != nil {
				t.Fatalf("read manifest: %v", err)
			}
			payload = bytes.Replace(payload, []byte(`${CODEX_HOME}`), replacement, 1)
			if err := os.WriteFile(manifestPath, payload, 0o644); err != nil {
				t.Fatalf("write manifest: %v", err)
			}
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid Unicode in bundle manifest was accepted")
			}
		})
	}
}

func TestLoadRejectsUnknownDependenciesAndOverlappingTargets(t *testing.T) {
	t.Run("dependency", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		manifest["dependencies"] = []string{"missing"}
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("unknown dependency was accepted")
		}
	})

	t.Run("overlap", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		units := manifest["install_units"].([]any)
		units = append(units, map[string]any{
			"id":     "codex.overlap",
			"kind":   "file",
			"source": "payload.txt",
			"target": map[string]any{"root": "codex-config", "path": "payload.txt/child"},
		})
		manifest["install_units"] = units
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("overlapping target was accepted")
		}
	})
}

func TestLoadRejectsNonCanonicalBundleIdentityAndMissingRuntimeProfile(t *testing.T) {
	t.Run("component identity", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		manifest["component"] = "codex/child"
		writeJSON(t, manifestPath, manifest, 0o644)
		indexPath := filepath.Join(root, "release.json")
		index := readObject(t, indexPath)
		entry := index["manifests"].([]any)[0].(map[string]any)
		entry["component"] = "codex/child"
		entry["sha256"] = digest(t, manifestPath)
		writeJSON(t, indexPath, index, 0o644)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("non-canonical component identity was accepted")
		}
	})

	t.Run("runtime profile", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		delete(manifest, "runtime_profile")
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("missing runtime profile was accepted")
		}
	})
}

func TestLoadRejectsMissingRequiredBundleCollections(t *testing.T) {
	for _, field := range []string{
		"dependencies",
		"install_units",
		"legacy_artifacts",
		"resources",
	} {
		t.Run(field, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			delete(manifest, field)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatalf("missing required field %q was accepted", field)
			}
		})
	}
}

func TestLoadRejectsInvalidSupportedObservationContracts(t *testing.T) {
	tests := map[string]struct {
		strategy string
		source   string
		payload  string
		apply    string
	}{
		"json strategy":     {strategy: "json-key-merge", source: "config.json", payload: "{}\n", apply: "unimplemented"},
		"manual strategy":   {strategy: "manual-action", apply: "unimplemented"},
		"supported apply":   {strategy: "seed-if-absent", source: "config.json", payload: "{}\n", apply: "supported"},
		"empty shell line":  {strategy: "shell-line", source: "config.json", payload: "", apply: "unimplemented"},
		"blank shell line":  {strategy: "shell-line", source: "config.json", payload: "  \t\n", apply: "unimplemented"},
		"CRLF shell line":   {strategy: "shell-line", source: "config.json", payload: "source env\r\n", apply: "unimplemented"},
		"invalid UTF-8":     {strategy: "shell-line", source: "config.json", payload: string([]byte{0xff}), apply: "unimplemented"},
		"NUL control":       {strategy: "shell-line", source: "config.json", payload: "source\x00env\n", apply: "unimplemented"},
		"separator control": {strategy: "shell-line", source: "config.json", payload: "\u001c\n", apply: "unimplemented"},
		"many shell lines":  {strategy: "shell-line", source: "config.json", payload: "first\nsecond\n", apply: "unimplemented"},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["strategy"] = test.strategy
			resource["observation"] = "supported"
			resource["apply"] = test.apply
			if test.source == "" {
				delete(resource, "source")
			} else {
				resource["source"] = test.source
				writeFile(t, filepath.Join(root, "bundles/codex", test.source), test.payload, 0o644)
				manifest["payload_files"] = []any{
					payloadRow(t, filepath.Join(root, "bundles/codex", test.source), test.source),
					payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
				}
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid supported observation contract was accepted")
			}
		})
	}
}
