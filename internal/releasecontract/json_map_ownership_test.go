package releasecontract_test

import (
	"path/filepath"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadCapturesJSONMapOwnership(t *testing.T) {
	root := writeOwnershipFixture(t)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	want := &releasecontract.JSONMapOwnership{
		MapPointer:            "/permissions",
		EntrySchema:           "decision-rule-v1",
		DesiredMap:            `{"read":"allow","write":{"*.md":"ask"}}`,
		RegistryTarget:        domain.Location{Root: "codex-config", Path: "ownership/permissions.json"},
		RegistrySchemaVersion: 1,
		EntriesPointer:        "/actions",
	}
	if got := release.Resources[0].JSONMapOwnership; !reflect.DeepEqual(got, want) {
		t.Fatalf("JSON map ownership = %#v, want %#v", got, want)
	}
}

func TestLoadRejectsInvalidDecisionRuleEntries(t *testing.T) {
	tests := map[string]string{
		"unknown decision":  `{"permissions":{"read":"permit"}}`,
		"scalar entry":      `{"permissions":{"read":true}}`,
		"empty pattern map": `{"permissions":{"read":{}}}`,
		"empty pattern":     `{"permissions":{"read":{"":"allow"}}}`,
		"pattern decision":  `{"permissions":{"read":{"*.md":"permit"}}}`,
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["ownership"] = ownershipRecord()
			configPath := filepath.Join(root, "bundles/codex/config.json")
			writeFile(t, configPath, payload+"\n", 0o644)
			manifest["payload_files"] = []any{
				payloadRow(t, configPath, "config.json"),
				payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid decision rule entry was accepted")
			}
		})
	}
}

func TestLoadRejectsInvalidOwnershipMapSource(t *testing.T) {
	for name, payload := range map[string]string{
		"missing": `{"other":{}}`,
		"array":   `{"permissions":[]}`,
		"null":    `{"permissions":null}`,
	} {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			manifest["resources"].([]any)[0].(map[string]any)["ownership"] = ownershipRecord()
			configPath := filepath.Join(root, "bundles/codex/config.json")
			writeFile(t, configPath, payload+"\n", 0o644)
			manifest["payload_files"] = []any{
				payloadRow(t, configPath, "config.json"),
				payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid ownership map source was accepted")
			}
		})
	}
}

func TestLoadRejectsStaticAndMapEntryOwnershipTogether(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["observation"] = "supported"
	resource["owned_json_pointers"] = []any{"/permissions"}
	resource["ownership"] = ownershipRecord()
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("two ownership models on one JSON resource were accepted")
	}
}

func TestLoadRejectsInvalidJSONMapOwnershipShapes(t *testing.T) {
	valid := ownershipRecord()
	tests := map[string]any{
		"null":                    nil,
		"unknown field":           mergeObject(valid, "extra", true),
		"missing kind":            withoutKey(valid, "kind"),
		"unknown kind":            mergeObject(valid, "kind", "future-registry"),
		"missing map pointer":     withoutKey(valid, "map_pointer"),
		"root map pointer":        mergeObject(valid, "map_pointer", ""),
		"invalid map pointer":     mergeObject(valid, "map_pointer", "/permissions/~2"),
		"missing entry schema":    withoutKey(valid, "entry_schema"),
		"unknown entry schema":    mergeObject(valid, "entry_schema", "future-rule"),
		"missing registry":        withoutKey(valid, "registry"),
		"unknown registry field":  ownershipWithRegistry(valid, "extra", true),
		"missing target":          ownershipWithoutRegistryKey(valid, "target"),
		"missing version":         ownershipWithoutRegistryKey(valid, "schema_version"),
		"unknown version":         ownershipWithRegistry(valid, "schema_version", 2),
		"missing entries pointer": ownershipWithoutRegistryKey(valid, "entries_pointer"),
		"root entries pointer":    ownershipWithRegistry(valid, "entries_pointer", ""),
		"invalid entries pointer": ownershipWithRegistry(valid, "entries_pointer", "/actions/~2"),
		"unknown entries pointer": ownershipWithRegistry(valid, "entries_pointer", "/other"),
	}
	for name, ownership := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeOwnershipFixture(t)
			setOwnership(t, root, ownership)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid JSON map ownership was accepted")
			}
		})
	}
}

func TestLoadRejectsJSONMapOwnershipForNonJSONResource(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["strategy"] = "ensure-directory"
	delete(resource, "source")
	resource["ownership"] = ownershipRecord()
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("JSON map ownership on non-JSON resource was accepted")
	}
}

func TestLoadRejectsJSONMapOwnershipWithoutSupportedObservation(t *testing.T) {
	root := writeOwnershipFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["observation"] = "unimplemented"
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("JSON map ownership without supported observation was accepted")
	}
}

func TestLoadRejectsJSONMapRegistryOutsideComponentRoot(t *testing.T) {
	root := writeOwnershipFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	ownership := resource["ownership"].(map[string]any)
	ownership = ownershipWithRegistry(ownership, "target", map[string]any{
		"root": "claude-config", "path": "ownership/permissions.json",
	})
	resource["ownership"] = ownership
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("foreign registry root was accepted")
	}
}

func TestLoadRejectsJSONMapRegistryOutsideResourceRoot(t *testing.T) {
	root := writeOwnershipFixture(t)
	rewriteFixtureTargets(t, root, "credential-tools", "home")
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	ownership := resource["ownership"].(map[string]any)
	resource["ownership"] = ownershipWithRegistry(
		ownership,
		"target",
		map[string]any{
			"root": "credentials-config",
			"path": "ownership/permissions.json",
		},
	)
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("ownership registry outside the resource root was accepted")
	}
}

func TestLoadRejectsJSONMapRegistryTargetCollisions(t *testing.T) {
	tests := map[string]func(map[string]any, map[string]any){
		"own JSON target": func(manifest, resource map[string]any) {
			ownership := resource["ownership"].(map[string]any)
			resource["ownership"] = ownershipWithRegistry(
				ownership,
				"target",
				cloneObject(resource["target"].(map[string]any)),
			)
		},
		"install target": func(manifest, resource map[string]any) {
			manifest["install_units"].([]any)[0].(map[string]any)["target"] =
				registryTarget(resource)
		},
		"resource target": func(manifest, resource map[string]any) {
			manifest["resources"] = append(manifest["resources"].([]any), map[string]any{
				"id": "codex.seed", "strategy": "seed-if-absent", "source": "config.json",
				"target": registryTarget(resource), "observation": "supported", "apply": "unimplemented",
			})
		},
		"other registry target": func(manifest, resource map[string]any) {
			second := cloneObject(resource)
			second["id"] = "codex.second"
			second["target"] = map[string]any{
				"root": "codex-config", "path": "other.json",
			}
			ownership := cloneObject(resource["ownership"].(map[string]any))
			ownership["map_pointer"] = "/other"
			second["ownership"] = ownership
			manifest["resources"] = append(manifest["resources"].([]any), second)
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeOwnershipFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			mutate(manifest, resource)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("registry target collision was accepted")
			}
		})
	}
}

func TestLoadClaimsOwnershipMapPointerGlobally(t *testing.T) {
	root := writeOwnershipFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	base := manifest["resources"].([]any)[0].(map[string]any)
	manifest["resources"] = append(manifest["resources"].([]any), map[string]any{
		"id": "codex.static", "strategy": "json-key-merge", "source": "config.json",
		"target": base["target"], "observation": "supported", "apply": "unimplemented",
		"owned_json_pointers": []any{"/permissions/read"},
	})
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("ownership map pointer overlap with a static JSON claim was accepted")
	}
}

func writeOwnershipFixture(t *testing.T) string {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["observation"] = "supported"
	resource["ownership"] = ownershipRecord()
	configPath := filepath.Join(root, "bundles/codex/config.json")
	writeFile(
		t,
		configPath,
		`{"other":{"read":"allow"},"permissions":{"read":"allow","write":{"*.md":"ask"}}}`+"\n",
		0o644,
	)
	manifest["payload_files"] = []any{
		payloadRow(t, configPath, "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	return root
}

func setOwnership(t *testing.T, root string, ownership any) {
	t.Helper()
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["resources"].([]any)[0].(map[string]any)["ownership"] = ownership
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
}

func ownershipRecord() map[string]any {
	return map[string]any{
		"kind":         "json-map-entry-registry-v1",
		"map_pointer":  "/permissions",
		"entry_schema": "decision-rule-v1",
		"registry": map[string]any{
			"target": map[string]any{
				"root": "codex-config", "path": "ownership/permissions.json",
			},
			"schema_version":  1,
			"entries_pointer": "/actions",
		},
	}
}

func registryTarget(resource map[string]any) map[string]any {
	ownership := resource["ownership"].(map[string]any)
	registry := ownership["registry"].(map[string]any)
	return cloneObject(registry["target"].(map[string]any))
}

func cloneObject(source map[string]any) map[string]any {
	result := make(map[string]any, len(source))
	for key, value := range source {
		result[key] = value
	}
	return result
}

func mergeObject(source map[string]any, key string, value any) map[string]any {
	result := cloneObject(source)
	result[key] = value
	return result
}

func withoutKey(source map[string]any, key string) map[string]any {
	result := cloneObject(source)
	delete(result, key)
	return result
}

func ownershipWithRegistry(source map[string]any, key string, value any) map[string]any {
	result := cloneObject(source)
	registry := cloneObject(result["registry"].(map[string]any))
	registry[key] = value
	result["registry"] = registry
	return result
}

func ownershipWithoutRegistryKey(source map[string]any, key string) map[string]any {
	result := cloneObject(source)
	registry := cloneObject(result["registry"].(map[string]any))
	delete(registry, key)
	result["registry"] = registry
	return result
}
