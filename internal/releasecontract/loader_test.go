package releasecontract_test

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
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
		raw := `{"schema_version":1,"schema_version":1,"kind":"mainframe-release","release_id":"test-release","manifests":[]}`
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
		"schema_version": 1,
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
	}
	manifestPath := filepath.Join(bundle, "bundle.json")
	writeJSON(t, manifestPath, manifest, 0o644)
	index := map[string]any{
		"schema_version": 1,
		"kind":           "mainframe-release",
		"release_id":     "test-release",
		"manifests": []any{map[string]any{
			"component": "codex",
			"path":      "bundles/codex/bundle.json",
			"sha256":    digest(t, manifestPath),
		}},
	}
	writeJSON(t, filepath.Join(root, "release.json"), index, 0o644)
	return root
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
