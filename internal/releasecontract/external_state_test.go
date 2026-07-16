package releasecontract_test

import (
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadCapturesCodexHookTrustExternalState(t *testing.T) {
	root := writeFixture(t)
	setCodexHookTrustResource(t, root, "codex-hook-trust-v1", "codex-config")

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	resource := release.Resources[0]
	want := &releasecontract.ExternalStateDescriptor{
		Kind: releasecontract.ExternalStateCodexHookTrust,
	}
	if !reflect.DeepEqual(resource.ExternalState, want) {
		t.Fatalf("external state = %#v, want %#v", resource.ExternalState, want)
	}
	if resource.SourcePath != "bundles/codex/hooks.json" ||
		resource.Strategy != releasecontract.StrategyManualAction ||
		resource.Observation != releasecontract.SupportSupported {
		t.Fatalf("resource = %#v", resource)
	}
}

func TestLoadRejectsInvalidExternalStateBoundaries(t *testing.T) {
	tests := map[string]struct {
		kind string
		root string
	}{
		"unknown kind":      {kind: "other-v1", root: "codex-config"},
		"cross adapter":     {kind: "codex-hook-trust-v1", root: "opencode-config"},
		"wrong target root": {kind: "codex-hook-trust-v1", root: "home"},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			setCodexHookTrustResource(t, root, test.kind, test.root)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid external-state resource was accepted")
			}
		})
	}
	t.Run("null descriptor", func(t *testing.T) {
		root := writeFixture(t)
		setCodexHookTrustResource(t, root, "codex-hook-trust-v1", "codex-config")
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		resource := manifest["resources"].([]any)[0].(map[string]any)
		resource["external_state"] = nil
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("null external-state descriptor was accepted")
		}
	})
	t.Run("mismatched install source", func(t *testing.T) {
		root := writeFixture(t)
		setCodexHookTrustResource(t, root, "codex-hook-trust-v1", "codex-config")
		manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
		manifest := readObject(t, manifestPath)
		resource := manifest["resources"].([]any)[0].(map[string]any)
		resource["source"] = "config.json"
		writeJSON(t, manifestPath, manifest, 0o644)
		rewriteIndexDigest(t, root, manifestPath)
		if _, err := releasecontract.Load(root); err == nil {
			t.Fatal("external state detached from its install unit was accepted")
		}
	})
}

func setCodexHookTrustResource(t *testing.T, root, kind, targetRoot string) {
	t.Helper()
	bundle := filepath.Join(root, "bundles/codex")
	hooksPath := filepath.Join(bundle, "hooks.json")
	writeFile(t, hooksPath, `{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"true"}]}]}}`+"\n", 0o644)
	manifestPath := filepath.Join(bundle, "bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["resources"] = []any{map[string]any{
		"id":       "codex.hook-trust",
		"strategy": "manual-action",
		"source":   "hooks.json",
		"target": map[string]any{
			"root": targetRoot,
			"path": "hooks.json",
		},
		"observation": "supported",
		"apply":       "unimplemented",
		"external_state": map[string]any{
			"kind": kind,
		},
	}}
	installUnits := append(
		manifest["install_units"].([]any),
		map[string]any{
			"id":     "codex.hooks",
			"kind":   "file",
			"source": "hooks.json",
			"target": map[string]any{
				"root": targetRoot,
				"path": "hooks.json",
			},
		},
	)
	sort.Slice(installUnits, func(left, right int) bool {
		return installUnits[left].(map[string]any)["id"].(string) <
			installUnits[right].(map[string]any)["id"].(string)
	})
	manifest["install_units"] = installUnits
	payloadFiles := append(
		manifest["payload_files"].([]any),
		payloadRow(t, hooksPath, "hooks.json"),
	)
	sort.Slice(payloadFiles, func(left, right int) bool {
		return payloadFiles[left].(map[string]any)["path"].(string) <
			payloadFiles[right].(map[string]any)["path"].(string)
	})
	manifest["payload_files"] = payloadFiles
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
}
