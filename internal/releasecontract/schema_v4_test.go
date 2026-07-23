package releasecontract_test

import (
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBundleSchemaV4HostRequirementsAreOptionalAndStrict(t *testing.T) {
	valid := []any{map[string]any{
		"kind":              "darwin-application-bundle-v1",
		"bundle_identifier": "com.example.Mainframe",
		"exact_versions":    []any{"1.0.0"},
	}}
	tests := map[string]struct {
		value   any
		present bool
		wantErr bool
	}{
		"absent":     {wantErr: false},
		"valid":      {value: valid, present: true, wantErr: false},
		"empty":      {value: []any{}, present: true, wantErr: true},
		"null":       {value: nil, present: true, wantErr: true},
		"wrong type": {value: map[string]any{}, present: true, wantErr: true},
		"unknown field": {
			value: []any{map[string]any{
				"kind":              "darwin-application-bundle-v1",
				"bundle_identifier": "com.example.Mainframe",
				"exact_versions":    []any{"1.0.0"},
				"other":             true,
			}},
			present: true,
			wantErr: true,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeExactJSONFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			if test.present {
				manifest["host_requirements"] = test.value
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			_, err := releasecontract.Load(root)
			if (err != nil) != test.wantErr {
				t.Fatalf("Load() error = %v, wantErr %t", err, test.wantErr)
			}
		})
	}
}

func TestExactJSONDocumentRejectsOverlappingManualAction(t *testing.T) {
	root := writeExactJSONFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resources := manifest["resources"].([]any)
	resources = append(resources, map[string]any{
		"id":          "codex.manual",
		"strategy":    "manual-action",
		"target":      map[string]any{"root": "codex-config", "path": "mainframe/diagnostics.json"},
		"observation": "unimplemented",
		"apply":       "unimplemented",
	})
	manifest["resources"] = resources
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("manual action overlapping an exact JSON document was accepted")
	}
}

func TestExactJSONDocumentRejectsNonDirectoryAncestor(t *testing.T) {
	root := writeExactJSONFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resources := manifest["resources"].([]any)
	resources = append([]any{map[string]any{
		"id":          "codex.container",
		"strategy":    "seed-if-absent",
		"source":      "diagnostics.json",
		"target":      map[string]any{"root": "codex-config", "path": "mainframe"},
		"observation": "supported",
		"apply":       "unimplemented",
	}}, resources...)
	manifest["resources"] = resources
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("non-directory ancestor of exact JSON document was accepted")
	}
}
