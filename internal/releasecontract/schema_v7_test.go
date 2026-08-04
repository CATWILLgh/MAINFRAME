package releasecontract_test

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBundleSchemaV7BoundsJSONClaimsPerTarget(t *testing.T) {
	root, manifestPath, manifest := jsonClaimFixture(t)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	ownership := resource["json_ownership"].(map[string]any)
	claims := make([]any, releasecontract.MaxOwnedJSONPointers+1)
	document := make(map[string]any, len(claims))
	for index := range claims {
		identifier := fmt.Sprintf("claim-%04d", index)
		pointer := fmt.Sprintf("/field-%04d", index)
		claims[index] = map[string]any{
			"id": identifier, "kind": "exact-scalar", "pointer": pointer,
		}
		document[fmt.Sprintf("field-%04d", index)] = true
	}
	ownership["claims"] = claims
	payload, err := json.Marshal(document)
	if err != nil {
		t.Fatal(err)
	}
	writeFile(
		t,
		filepath.Join(root, "bundles/codex/config.json"),
		string(payload),
		0o644,
	)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("Load() accepted too many JSON claims")
	}
}

func TestBundleSchemaV7LoadsGenericJSONClaimOwnership(t *testing.T) {
	root := writeFixture(t)
	rewriteFixtureTargets(t, root, "zcode-desktop", "zcode-config")
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 7
	manifest["dependencies"] = []any{}
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["id"] = "zcode.hooks"
	resource["target"] = map[string]any{"root": "zcode-config", "path": "cli/config.json"}
	resource["observation"] = "supported"
	resource["apply"] = "supported"
	resource["json_ownership"] = jsonClaimOwnershipRecord()
	payload := `{"hooks":{"enabled":true,"events":{"SessionStart":[{"hooks":[{"args":["_zcode-hook","SessionStart"]}]}]}}}` + "\n"
	writeFile(t, filepath.Join(root, "bundles/codex/config.json"), payload, 0o644)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	ownership := release.Resources[0].JSONClaimOwnership
	if ownership == nil || ownership.RegistryTarget != (domain.Location{
		Root: domain.RootZCodeConfig, Path: "mainframe/config-ownership.json",
	}) || len(ownership.Claims) != 2 || ownership.Claims[1].SelectorValue != `"SessionStart"` {
		t.Fatalf("JSON claim ownership = %#v", ownership)
	}
}

func TestBundleSchemaV7RejectsInvalidJSONClaimOwnership(t *testing.T) {
	tests := map[string]func(map[string]any){
		"schema v6": func(manifest map[string]any) { manifest["schema_version"] = 6 },
		"foreign registry": func(manifest map[string]any) {
			ownership := manifest["resources"].([]any)[0].(map[string]any)["json_ownership"].(map[string]any)
			ownership["registry"].(map[string]any)["target"].(map[string]any)["root"] = "codex-config"
		},
		"unknown claim field": func(manifest map[string]any) {
			claim := manifest["resources"].([]any)[0].(map[string]any)["json_ownership"].(map[string]any)["claims"].([]any)[0].(map[string]any)
			claim["unknown"] = true
		},
		"root claim pointer": func(manifest map[string]any) {
			ownership := manifest["resources"].([]any)[0].(map[string]any)["json_ownership"].(map[string]any)
			claim := ownership["claims"].([]any)[0].(map[string]any)
			claim["pointer"] = ""
			ownership["claims"] = []any{claim}
		},
		"claim pointer traverses array": func(manifest map[string]any) {
			ownership := manifest["resources"].([]any)[0].(map[string]any)["json_ownership"].(map[string]any)
			claim := ownership["claims"].([]any)[0].(map[string]any)
			claim["kind"] = "exact-scalar"
			claim["pointer"] = "/hooks/events/SessionStart/0/hooks/0/args/1"
			ownership["claims"] = []any{claim}
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root, manifestPath, manifest := jsonClaimFixture(t)
			mutate(manifest)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("Load() accepted invalid JSON claim ownership")
			}
		})
	}
}

func jsonClaimFixture(t *testing.T) (string, string, map[string]any) {
	t.Helper()
	root := writeFixture(t)
	rewriteFixtureTargets(t, root, "zcode-desktop", "zcode-config")
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 7
	manifest["dependencies"] = []any{}
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["id"] = "zcode.hooks"
	resource["target"] = map[string]any{"root": "zcode-config", "path": "cli/config.json"}
	resource["observation"] = "supported"
	resource["apply"] = "supported"
	resource["json_ownership"] = jsonClaimOwnershipRecord()
	payload := `{"hooks":{"enabled":true,"events":{"SessionStart":[{"hooks":[{"args":["_zcode-hook","SessionStart"]}]}]}}}` + "\n"
	if err := os.WriteFile(filepath.Join(root, "bundles/codex/config.json"), []byte(payload), 0o644); err != nil {
		t.Fatal(err)
	}
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	return root, manifestPath, manifest
}

func jsonClaimOwnershipRecord() map[string]any {
	return map[string]any{
		"kind": "json-claim-registry-v1",
		"registry": map[string]any{
			"target":         map[string]any{"root": "zcode-config", "path": "mainframe/config-ownership.json"},
			"schema_version": 1,
		},
		"claims": []any{
			map[string]any{"id": "hooks-enabled", "kind": "exact-scalar", "pointer": "/hooks/enabled"},
			map[string]any{
				"id": "session-start", "kind": "array-entry", "pointer": "/hooks/events/SessionStart",
				"selector": map[string]any{"pointer": "/hooks/0/args/1", "value": "SessionStart"},
			},
		},
	}
}
