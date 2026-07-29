//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

const legacySecretValueCanary = "SYNTHETIC_SECRET_VALUE_CANARY"

type legacyApplyFixture struct {
	t           *testing.T
	sourcePath  string
	catalogPath string
	stateRoot   string
}

type legacyApplyReview struct {
	ApplyAvailable              bool            `json:"apply_available"`
	ManualContentReviewRequired bool            `json:"manual_content_review_required"`
	RetirementReady             bool            `json:"retirement_ready"`
	ApplyRequest                json.RawMessage `json:"apply_request"`
	ExpectedReview              string          `json:"expected_review"`
	Changes                     []any           `json:"changes"`
	raw                         string
}

type legacySourceSnapshot struct {
	content []byte
	mode    fs.FileMode
	device  uint64
	inode   uint64
	birth   string
}

func newLegacyApplyFixture(t *testing.T) legacyApplyFixture {
	t.Helper()
	release := writePlanReleaseFixture(t)
	addLegacyResourcesToRelease(t, release.root)
	t.Setenv(releaseRootEnvironment, release.root)
	home, config, state := canonicalTempDir(t), canonicalTempDir(t), canonicalTempDir(t)
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", filepath.Join(home, ".codex"))
	t.Setenv("XDG_CONFIG_HOME", config)
	t.Setenv("XDG_STATE_HOME", state)
	t.Setenv("LEGACY_ALPHA", legacySecretValueCanary)
	t.Setenv("LEGACY_BETA", legacySecretValueCanary)
	source := filepath.Join(home, ".claude", "credentials-index.md")
	writeFixtureFile(t, source, []byte(legacySourceContent()), 0o600)
	return legacyApplyFixture{
		t: t, sourcePath: source,
		catalogPath: filepath.Join(config, "credentials", "mainframe", "instances.json"),
		stateRoot:   filepath.Join(state, "mainframe"),
	}
}

func addLegacyResourcesToRelease(t *testing.T, root string) {
	t.Helper()
	release := readJSONMap(t, filepath.Join(root, "release.json"))
	manifests := release["manifests"].([]any)
	for _, raw := range manifests {
		entry := raw.(map[string]any)
		component := entry["component"].(string)
		if legacyRootForComponent(component) == "" {
			continue
		}
		path := filepath.Join(root, filepath.FromSlash(entry["path"].(string)))
		addLegacyResourceToBundle(t, path, component)
		entry["sha256"] = fixtureDigest(t, path)
	}
	writeFixtureJSON(t, filepath.Join(root, "release.json"), release, 0o644)
}

func addLegacyResourceToBundle(t *testing.T, path, component string) {
	t.Helper()
	bundle := readJSONMap(t, path)
	source := filepath.Join(filepath.Dir(path), "credentials-index.md")
	writeFixtureFile(t, source, []byte("release template\n"), 0o644)
	bundle["resources"] = []any{map[string]any{
		"id": component + ".credentials-index", "strategy": "seed-if-absent",
		"source": "credentials-index.md",
		"target": map[string]any{
			"root": legacyRootForComponent(component), "path": "credentials-index.md",
		},
		"observation": "unimplemented", "apply": "unimplemented",
	}}
	rows := bundle["payload_files"].([]any)
	bundle["payload_files"] = append(rows, fixturePayloadRow(t, source, "credentials-index.md"))
	writeFixtureJSON(t, path, bundle, 0o644)
}

func legacyRootForComponent(component string) string {
	return map[string]string{
		"antigravity-2": "antigravity-data",
		"claude-code":   "claude-config",
		"codex":         "codex-config",
		"opencode":      "opencode-config",
	}[component]
}

func readJSONMap(t *testing.T, path string) map[string]any {
	t.Helper()
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read JSON fixture: %v", err)
	}
	var result map[string]any
	if err := json.Unmarshal(payload, &result); err != nil {
		t.Fatalf("decode JSON fixture: %v", err)
	}
	return result
}

func legacySourceContent() string {
	return "# Catalog\n\n## Home\n- `secret get LEGACY_ALPHA`\n\n" +
		"## Work\n- `secret get LEGACY_BETA`\n"
}

func (fixture legacyApplyFixture) completeReview() legacyApplyReview {
	fixture.t.Helper()
	return fixture.review(legacyReviewPayload(true, false))
}

func (fixture legacyApplyFixture) review(payload []byte) legacyApplyReview {
	fixture.t.Helper()
	exit, stdout, stderr := runCredentialCommand(
		[]string{"credentials", "legacy-review"}, payload,
	)
	if exit != 0 {
		fixture.t.Fatalf("legacy review exit = %d, stderr = %q", exit, stderr)
	}
	var review legacyApplyReview
	if err := json.Unmarshal([]byte(stdout), &review); err != nil {
		fixture.t.Fatalf("decode legacy review: %v; output = %q", err, stdout)
	}
	review.raw = stdout
	return review
}

func legacyReviewPayload(transfer, existing bool) []byte {
	instances := []any{}
	if transfer && !existing {
		instances = []any{
			legacyInstance("context7-home", "Home", "LEGACY_ALPHA"),
			legacyInstance("context7-work", "Work", "LEGACY_BETA"),
		}
	}
	choices := []any{
		legacyChoice("Home", "LEGACY_ALPHA", transfer, "context7-home"),
		legacyChoice("Work", "LEGACY_BETA", transfer, "context7-work"),
	}
	payload, _ := json.Marshal(map[string]any{
		"schema_version": 1,
		"kind":           "mainframe-legacy-credential-transfer-draft",
		"release_id":     "cli-plan-test",
		"new_instances":  instances,
		"choices":        choices,
	})
	return payload
}

func legacyInstance(id, name, reference string) map[string]any {
	return map[string]any{
		"id": id, "service_id": "context7", "name": name,
		"purpose": name + " research",
		"credentials": []any{map[string]any{
			"role_id": "api-key",
			"secret":  map[string]any{"backend": "secret-env", "name": reference},
		}},
	}
}

func legacyChoice(section, reference string, transfer bool, target string) map[string]any {
	choice := map[string]any{
		"proposal": map[string]any{
			"component_id":   "claude-code",
			"resource_id":    "claude-code.credentials-index",
			"source_role":    "shared_original",
			"section_path":   []string{"Catalog", section},
			"reference_name": reference,
		},
		"expected_occurrences": 1,
	}
	if transfer {
		choice["action"] = "transfer"
		choice["target"] = map[string]any{"instance_id": target, "role_id": "api-key"}
	} else {
		choice["action"] = "skip"
		choice["target"] = map[string]any{}
		choice["skip_reason"] = "obsolete"
	}
	return choice
}

func runCredentialCommand(args []string, payload []byte) (int, string, string) {
	var stdout, stderr bytes.Buffer
	exit := run(args, bytes.NewReader(payload), &stdout, &stderr)
	return exit, stdout.String(), stderr.String()
}

func (fixture legacyApplyFixture) apply(review legacyApplyReview, digest string) (int, string, string) {
	fixture.t.Helper()
	return runCredentialCommand(
		[]string{"credentials", "legacy-apply", "--confirm", digest},
		review.ApplyRequest,
	)
}

func snapshotLegacySource(t *testing.T, path string) legacySourceSnapshot {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read legacy source: %v", err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat legacy source: %v", err)
	}
	value := reflect.ValueOf(info.Sys())
	if value.Kind() == reflect.Pointer {
		value = value.Elem()
	}
	return legacySourceSnapshot{
		content: content, mode: info.Mode(),
		device: reflectedUint(value, "Dev"), inode: reflectedUint(value, "Ino"),
		birth: reflectedString(value, "Birthtimespec"),
	}
}

func reflectedUint(value reflect.Value, name string) uint64 {
	field := value.FieldByName(name)
	if !field.IsValid() {
		return 0
	}
	return field.Convert(reflect.TypeOf(uint64(0))).Uint()
}

func reflectedString(value reflect.Value, name string) string {
	field := value.FieldByName(name)
	if !field.IsValid() {
		return ""
	}
	return fmt.Sprint(field.Interface())
}
