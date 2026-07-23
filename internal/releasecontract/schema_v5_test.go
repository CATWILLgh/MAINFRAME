package releasecontract_test

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBundleSchemaV5PreservesInstallUnitFeature(t *testing.T) {
	root := writeExactJSONFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 5
	unit := manifest["install_units"].([]any)[0].(map[string]any)
	unit["feature"] = string(domain.FeatureHarnessFeedback)
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load(): %v", err)
	}
	artifacts := release.Model.Artifacts()
	if len(artifacts) != 2 {
		t.Fatalf("artifacts = %#v", artifacts)
	}
	var feature domain.FeatureID
	for _, artifact := range artifacts {
		if !artifact.LegacyOnly {
			feature = artifact.Feature
		}
	}
	if feature != domain.FeatureHarnessFeedback {
		t.Fatalf("feature = %q", feature)
	}
	component, _ := release.Model.Catalog().Component(domain.ComponentCodex)
	if len(component.Artifacts) != 1 ||
		component.Artifacts[0].Feature != domain.FeatureHarnessFeedback {
		t.Fatalf("catalog component = %#v", component)
	}
}

func TestBundleInstallUnitFeatureFailsClosed(t *testing.T) {
	tests := []struct {
		name          string
		schemaVersion int
		feature       string
		message       string
	}{
		{name: "v4 field", schemaVersion: 4, feature: string(domain.FeatureHarnessFeedback), message: "feature"},
		{name: "invalid identifier", schemaVersion: 5, feature: "Harness_Feedback", message: "feature"},
		{name: "empty identifier", schemaVersion: 5, feature: "", message: "feature"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			manifest["schema_version"] = test.schemaVersion
			manifest["install_units"].([]any)[0].(map[string]any)["feature"] = test.feature
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)

			_, err := releasecontract.Load(root)
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("Load() error = %v, want %q", err, test.message)
			}
		})
	}

	t.Run("null feature", func(t *testing.T) {
		root := writeFixture(t)
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		manifest["schema_version"] = 5
		manifest["install_units"].([]any)[0].(map[string]any)["feature"] = nil
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)

		_, err := releasecontract.Load(root)
		if err == nil || !strings.Contains(err.Error(), "feature") {
			t.Fatalf("Load() error = %v, want feature error", err)
		}
	})
}
