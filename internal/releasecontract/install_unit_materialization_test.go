package releasecontract_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadInstallUnitMaterialization(t *testing.T) {
	t.Run("writable file", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		manifest["schema_version"] = 8
		unit := manifest["install_units"].([]any)[0].(map[string]any)
		unit["materialization"] = "writable-file"
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)

		release, err := releasecontract.Load(root)
		if err != nil {
			t.Fatalf("load writable-file unit: %v", err)
		}
		artifacts := release.Model.Artifacts()
		if len(artifacts) != 2 || artifacts[1].Materialization != domain.MaterializationWritableFile ||
			artifacts[1].SourceSHA256 != digest(t, filepath.Join(root, "bundles/codex/payload.txt")) {
			t.Fatalf("artifacts = %#v", artifacts)
		}
	})

	for name, value := range map[string]string{
		"unknown": "copy",
		"tree":    "writable-file",
	} {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			unit := manifest["install_units"].([]any)[0].(map[string]any)
			unit["materialization"] = value
			if name == "tree" {
				unit["kind"] = "tree"
				unit["source"] = "tree"
				if err := os.Mkdir(filepath.Join(root, "bundles/codex/tree"), 0o755); err != nil {
					t.Fatalf("mkdir tree: %v", err)
				}
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatalf("materialization %q was accepted for %s", value, name)
			}
		})
	}
}

func TestLoadRejectsMaterializationBeforeSchemaEight(t *testing.T) {
	for _, value := range []string{"", "symlink", "writable-file"} {
		t.Run(value, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			manifest["schema_version"] = 7
			unit := manifest["install_units"].([]any)[0].(map[string]any)
			unit["materialization"] = value
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatalf("schema 7 accepted explicit materialization %q", value)
			}
		})
	}
}
