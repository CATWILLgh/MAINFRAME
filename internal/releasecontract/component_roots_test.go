package releasecontract_test

import (
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadRejectsComponentTargetingUnownedRoot(t *testing.T) {
	for _, targetRoot := range []string{"claude-config", "unknown-root"} {
		for _, collection := range []string{"install_units", "legacy_artifacts", "resources"} {
			t.Run(targetRoot+"/"+collection, func(t *testing.T) {
				root := writeFixture(t)
				rewriteFixtureTargets(t, root, "codex", "codex-config")
				manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
				manifest := readObject(t, manifestPath)
				records := manifest[collection].([]any)
				records[0].(map[string]any)["target"] = map[string]any{
					"root": targetRoot, "path": "foreign",
				}
				writeJSON(t, manifestPath, manifest, 0o644)
				rewriteIndexDigest(t, root, manifestPath)

				if _, err := releasecontract.Load(root); err == nil {
					t.Fatalf("Codex %s targeting root %q was accepted", collection, targetRoot)
				}
			})
		}
	}
}

func TestLoadAcceptsDeclaredComponentRoots(t *testing.T) {
	allowed := map[string][]string{
		"antigravity-2":    {"antigravity-config", "antigravity-data"},
		"claude-code":      {"claude-config"},
		"codex":            {"codex-config"},
		"credential-tools": {"credentials-config", "home", "user-bin"},
		"mainframe-cli":    {"user-bin"},
		"opencode":         {"opencode-config"},
	}
	for component, roots := range allowed {
		for _, targetRoot := range roots {
			t.Run(component+"/"+targetRoot, func(t *testing.T) {
				root := writeFixture(t)
				rewriteFixtureTargets(t, root, component, targetRoot)
				if _, err := releasecontract.Load(root); err != nil {
					t.Fatalf("load supported component root: %v", err)
				}
			})
		}
	}
}

func TestLoadRejectsUnknownComponent(t *testing.T) {
	root := writeFixture(t)
	rewriteFixtureTargets(t, root, "unknown", "codex-config")
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("unknown release component was accepted")
	}
}

func TestLoadRejectsCredentialToolsHomeEscape(t *testing.T) {
	for _, collection := range []string{"install_units", "legacy_artifacts", "resources"} {
		t.Run(collection, func(t *testing.T) {
			root := writeFixture(t)
			rewriteFixtureTargets(t, root, "credential-tools", "home")
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			record := manifest[collection].([]any)[0].(map[string]any)
			target := record["target"].(map[string]any)
			target["path"] = ".claude/settings.json"
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)

			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("credential-tools home escape was accepted")
			}
		})
	}
}

func rewriteFixtureTargets(t *testing.T, root, component, targetRoot string) {
	t.Helper()
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["component"] = component
	for index, collection := range []string{"install_units", "legacy_artifacts", "resources"} {
		for _, raw := range manifest[collection].([]any) {
			target := raw.(map[string]any)["target"].(map[string]any)
			target["root"] = targetRoot
			if targetRoot == "home" {
				target["path"] = []string{".bashrc", ".profile", ".zshenv"}[index]
			}
		}
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	indexPath := filepath.Join(root, "release.json")
	index := readObject(t, indexPath)
	entry := index["manifests"].([]any)[0].(map[string]any)
	entry["component"] = component
	entry["sha256"] = digest(t, manifestPath)
	writeJSON(t, indexPath, index, 0o644)
}
