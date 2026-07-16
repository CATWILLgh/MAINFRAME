package releasecontract_test

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadAcceptsSupportedShellObservationAndCapturesDesiredLine(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	writeFile(t, filepath.Join(root, "bundles/codex/source-line"), "source ~/.config/mainframe/env\n", 0o644)
	manifest["resources"] = []any{map[string]any{
		"id":          "codex.shell-source",
		"strategy":    "shell-line",
		"source":      "source-line",
		"target":      map[string]any{"root": "codex-config", "path": "shell-source"},
		"observation": "supported",
		"apply":       "unimplemented",
	}}
	manifest["payload_files"] = append(
		manifest["payload_files"].([]any),
		payloadRow(t, filepath.Join(root, "bundles/codex/source-line"), "source-line"),
	)
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	resource := release.Resources[0]
	if resource.Observation != releasecontract.SupportSupported {
		t.Fatalf("observation = %q", resource.Observation)
	}
	if resource.DesiredLine != "source ~/.config/mainframe/env" {
		t.Fatalf("desired line = %q", resource.DesiredLine)
	}
}

func TestLoadCapturesSupportedOwnedJSONFields(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["observation"] = "supported"
	resource["owned_json_pointers"] = []any{"/permissions/allow", "/permissions/deny"}
	writeFile(
		t,
		filepath.Join(root, "bundles/codex/config.json"),
		`{"user_setting":true,"permissions":{"deny":["Write"],"allow":["Read"]}}`+"\n",
		0o644,
	)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)

	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	want := []releasecontract.JSONField{
		{Pointer: "/permissions/allow", Desired: `["Read"]`},
		{Pointer: "/permissions/deny", Desired: `["Write"]`},
	}
	if got := release.Resources[0].OwnedJSONFields; !reflect.DeepEqual(got, want) {
		t.Fatalf("owned JSON fields = %#v, want %#v", got, want)
	}
}

func TestLoadRejectsInvalidOwnedJSONContracts(t *testing.T) {
	tests := map[string]struct {
		pointers []any
		payload  []byte
	}{
		"missing pointers":       {payload: []byte(`{"permissions":{"allow":[]}}`)},
		"empty pointers":         {pointers: []any{}, payload: []byte(`{"permissions":{"allow":[]}}`)},
		"root pointer":           {pointers: []any{""}, payload: []byte(`{}`)},
		"invalid escape":         {pointers: []any{"/permissions/~2"}, payload: []byte(`{"permissions":{}}`)},
		"unsorted pointers":      {pointers: []any{"/b", "/a"}, payload: []byte(`{"a":1,"b":2}`)},
		"overlapping pointers":   {pointers: []any{"/permissions", "/permissions/allow"}, payload: []byte(`{"permissions":{"allow":[]}}`)},
		"missing desired field":  {pointers: []any{"/permissions/deny"}, payload: []byte(`{"permissions":{}}`)},
		"array traversal":        {pointers: []any{"/permissions/0"}, payload: []byte(`{"permissions":[true]}`)},
		"duplicate source key":   {pointers: []any{"/permissions"}, payload: []byte(`{"permissions":1,"permissions":2}`)},
		"invalid source UTF-8":   {pointers: []any{"/permissions"}, payload: []byte{'{', '"', 'x', '"', ':', '"', 0xff, '"', '}'}},
		"unpaired source escape": {pointers: []any{"/permissions"}, payload: []byte(`{"permissions":"\uD800"}`)},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["observation"] = "supported"
			if test.pointers != nil {
				resource["owned_json_pointers"] = test.pointers
			}
			configPath := filepath.Join(root, "bundles/codex/config.json")
			if err := os.WriteFile(configPath, test.payload, 0o644); err != nil {
				t.Fatalf("write config: %v", err)
			}
			manifest["payload_files"] = []any{
				payloadRow(t, configPath, "config.json"),
				payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("invalid owned JSON contract was accepted")
			}
		})
	}
}

func TestLoadRejectsTooManyOwnedJSONPointers(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["observation"] = "supported"
	pointers := make([]any, 1025)
	for index := range pointers {
		pointers[index] = fmt.Sprintf("/field-%04d", index)
	}
	resource["owned_json_pointers"] = pointers
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("too many owned JSON pointers were accepted")
	}
}

func TestLoadBoundsAggregateOwnedJSONPointersPerTarget(t *testing.T) {
	if err := loadOwnedJSONCounts(t, 512, 512); err != nil {
		t.Fatalf("Load() rejected 1024 aggregate pointers: %v", err)
	}
	if err := loadOwnedJSONCounts(t, 512, 513); err == nil {
		t.Fatal("Load() accepted 1025 aggregate pointers")
	}
}

func loadOwnedJSONCounts(t *testing.T, firstCount, secondCount int) error {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	base := manifest["resources"].([]any)[0].(map[string]any)
	base["id"] = "codex.json-a"
	base["observation"] = "supported"
	base["owned_json_pointers"] = ownedPointers(0, firstCount)
	second := map[string]any{
		"id": "codex.json-b", "strategy": "json-key-merge", "source": "config.json",
		"target": base["target"], "observation": "supported", "apply": "unimplemented",
		"owned_json_pointers": ownedPointers(firstCount, secondCount),
	}
	manifest["resources"] = []any{base, second}
	document := make(map[string]any, firstCount+secondCount)
	for index := 0; index < firstCount+secondCount; index++ {
		document[fmt.Sprintf("field-%04d", index)] = nil
	}
	configPath := filepath.Join(root, "bundles/codex/config.json")
	writeJSON(t, configPath, document, 0o644)
	manifest["payload_files"] = []any{
		payloadRow(t, configPath, "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	_, err := releasecontract.Load(root)
	return err
}

func ownedPointers(start, count int) []any {
	pointers := make([]any, count)
	for index := range pointers {
		pointers[index] = fmt.Sprintf("/field-%04d", start+index)
	}
	return pointers
}

func TestLoadRejectsOwnedJSONPointerFieldOutsideSupportedJSON(t *testing.T) {
	for name, strategy := range map[string]string{
		"unimplemented JSON": "json-key-merge",
		"non-JSON":           "ensure-directory",
	} {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			resource["strategy"] = strategy
			resource["owned_json_pointers"] = []any{}
			if strategy != "json-key-merge" {
				delete(resource, "source")
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("owned JSON pointer field was accepted outside supported JSON")
			}
		})
	}
}

func TestLoadRejectsJSONResourceOverlapWithInstallTarget(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["target"] = map[string]any{"root": "codex-config", "path": "managed/config.json"}
	resource["observation"] = "supported"
	resource["owned_json_pointers"] = []any{"/permissions"}
	manifest["install_units"].([]any)[0].(map[string]any)["target"] =
		map[string]any{"root": "codex-config", "path": "managed"}
	writeFile(t, filepath.Join(root, "bundles/codex/config.json"), `{"permissions":[]}`+"\n", 0o644)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("overlapping JSON and install targets were accepted")
	}
}

func TestLoadRejectsOverlappingJSONOwnershipAcrossResources(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	base := manifest["resources"].([]any)[0].(map[string]any)
	base["id"] = "codex.permissions"
	base["observation"] = "supported"
	base["owned_json_pointers"] = []any{"/permissions"}
	second := map[string]any{
		"id":                  "codex.permissions-allow",
		"strategy":            "json-key-merge",
		"source":              "config.json",
		"target":              base["target"],
		"observation":         "supported",
		"apply":               "unimplemented",
		"owned_json_pointers": []any{"/permissions/allow"},
	}
	manifest["resources"] = []any{base, second}
	writeFile(
		t,
		filepath.Join(root, "bundles/codex/config.json"),
		`{"permissions":{"allow":[]}}`+"\n",
		0o644,
	)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("overlapping JSON ownership across resources was accepted")
	}
}

func TestLoadRejectsStructurallyIncompatibleJSONResourceTargets(t *testing.T) {
	tests := map[string]map[string]any{
		"ancestor JSON target": {
			"id":                  "codex.peer",
			"strategy":            "json-key-merge",
			"source":              "config.json",
			"target":              map[string]any{"root": "codex-config", "path": "config.json/child"},
			"observation":         "supported",
			"apply":               "unimplemented",
			"owned_json_pointers": []any{"/peer"},
		},
		"same target seed": {
			"id":          "codex.seed",
			"strategy":    "seed-if-absent",
			"source":      "config.json",
			"target":      map[string]any{"root": "codex-config", "path": "config.json"},
			"observation": "supported",
			"apply":       "unimplemented",
		},
	}
	for name, second := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			base := manifest["resources"].([]any)[0].(map[string]any)
			base["id"] = "codex.json"
			base["observation"] = "supported"
			base["owned_json_pointers"] = []any{"/owned"}
			manifest["resources"] = []any{base, second}
			writeFile(
				t,
				filepath.Join(root, "bundles/codex/config.json"),
				`{"owned":true,"peer":true}`+"\n",
				0o644,
			)
			manifest["payload_files"] = []any{
				payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
				payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
			}
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("structurally incompatible JSON resource targets were accepted")
			}
		})
	}
}

func TestLoadAllowsDirectoryResourceAboveJSONTarget(t *testing.T) {
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	jsonResource := manifest["resources"].([]any)[0].(map[string]any)
	jsonResource["id"] = "codex.json"
	jsonResource["target"] = map[string]any{
		"root": "codex-config", "path": "managed/config.json",
	}
	jsonResource["observation"] = "supported"
	jsonResource["owned_json_pointers"] = []any{"/owned"}
	directory := map[string]any{
		"id":          "codex.directory",
		"strategy":    "ensure-directory",
		"target":      map[string]any{"root": "codex-config", "path": "managed"},
		"observation": "supported",
		"apply":       "unimplemented",
	}
	manifest["resources"] = []any{directory, jsonResource}
	writeFile(t, filepath.Join(root, "bundles/codex/config.json"), `{"owned":true}`+"\n", 0o644)
	manifest["payload_files"] = []any{
		payloadRow(t, filepath.Join(root, "bundles/codex/config.json"), "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err != nil {
		t.Fatalf("parent directory resource was rejected: %v", err)
	}
}
