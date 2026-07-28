//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectLegacyCredentialIndexesUsesExactAdapterRoots(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", filepath.Join(home, "custom-codex"))
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, "custom-config"))
	release := legacyCredentialReleaseFixture()
	writeLegacyIndex(t, home, ".claude/credentials-index.md", "claude", 0o600)
	writeLegacyIndex(
		t,
		home,
		"custom-codex/credentials-index.md",
		"customized",
		0o600,
	)
	writeLegacyIndex(
		t,
		home,
		".gemini/antigravity/credentials-index.md",
		"antigravity",
		0o644,
	)

	inventory, err := inspectLegacyCredentialIndexes(
		release,
		t.TempDir(),
		hostEnvironment(),
	)
	if err != nil {
		t.Fatalf("inspectLegacyCredentialIndexes() error = %v", err)
	}
	states := []credentialmigration.IndexState{
		inventory.Indexes[0].State,
		inventory.Indexes[1].State,
		inventory.Indexes[2].State,
		inventory.Indexes[3].State,
	}
	want := []credentialmigration.IndexState{
		credentialmigration.IndexPresent,
		credentialmigration.IndexPresent,
		credentialmigration.IndexMissing,
		credentialmigration.IndexUnsafe,
	}
	if strings.Join(indexStates(states), ",") !=
		strings.Join(indexStates(want), ",") {
		t.Fatalf("states = %v, want %v", states, want)
	}
	if !inventory.Indexes[0].MatchesCurrentTemplate ||
		inventory.Indexes[1].MatchesCurrentTemplate ||
		inventory.Indexes[3].UnsafeReason !=
			credentialmigration.ReasonUnsafeMode {
		t.Fatalf("inventory = %#v", inventory)
	}
}

func TestPublicLegacyCredentialInventoryHasValueFreeContract(t *testing.T) {
	canary := "legacy-private-canary"
	inventory := credentialmigration.Inventory{
		ReleaseID:          "release-a",
		ReleaseIndexSHA256: strings.Repeat("a", 64),
		Indexes: []credentialmigration.LegacyIndex{{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			Location: domain.Location{
				Root: domain.RootClaudeConfig,
				Path: "credentials-index.md",
			},
			SourceRole:             credentialmigration.SourceRoleSharedOriginal,
			State:                  credentialmigration.IndexPresent,
			SizeBytes:              len(canary),
			MatchesCurrentTemplate: false,
			MigrationReadiness: credentialmigration.
				ReadinessManualTransferRequired,
		}},
		MigrationReadiness: credentialmigration.ReadinessManualTransferRequired,
	}
	var output bytes.Buffer
	if err := writeLegacyCredentialInventory(&output, inventory); err != nil {
		t.Fatalf("writeLegacyCredentialInventory() error = %v", err)
	}
	var response map[string]any
	if err := json.Unmarshal(output.Bytes(), &response); err != nil {
		t.Fatalf("decode inventory output: %v", err)
	}
	if response["kind"] != "mainframe-legacy-credential-index-inventory" ||
		response["scope"] != "historical-credential-locations" ||
		response["schema_version"] != float64(3) ||
		response["migration_performed"] != false ||
		response["migration_readiness"] != "manual_transfer_required" {
		t.Fatalf("legacy inventory response = %s", output.String())
	}
	for _, forbidden := range []string{
		canary,
		"content_sha256",
		"absolute_path",
		"symlink_target",
		"raw_error",
	} {
		if strings.Contains(output.String(), forbidden) {
			t.Fatalf("legacy inventory exposed %q: %s", forbidden, output.String())
		}
	}
	indexes, ok := response["indexes"].([]any)
	if !ok || len(indexes) != 1 {
		t.Fatalf("legacy inventory indexes = %#v", response["indexes"])
	}
	assertLegacyIndexResponseKeys(t, indexes[0])
	index := indexes[0].(map[string]any)
	if index["migration_readiness"] != "manual_transfer_required" {
		t.Fatalf("legacy index readiness = %#v", index)
	}
	if index["source_role"] != "shared_original" {
		t.Fatalf("legacy index source role = %#v", index)
	}
}

func assertLegacyIndexResponseKeys(t *testing.T, raw any) {
	t.Helper()
	index, ok := raw.(map[string]any)
	if !ok {
		t.Fatalf("legacy index response = %#v", raw)
	}
	allowed := map[string]bool{
		"component_id":                     true,
		"resource_id":                      true,
		"location":                         true,
		"state":                            true,
		"size_bytes":                       true,
		"matches_current_release_template": true,
		"unsafe_reason":                    true,
		"migration_readiness":              true,
		"source_role":                      true,
	}
	for key := range index {
		if !allowed[key] {
			t.Fatalf("legacy index exposes unexpected field %q", key)
		}
	}
}

func TestLegacyCredentialCommandDoesNotExposeSetupErrors(t *testing.T) {
	privatePath := filepath.Join(t.TempDir(), "legacy-private-canary")
	t.Setenv(releaseRootEnvironment, privatePath)
	var stdout, stderr bytes.Buffer

	exitCode := run(
		[]string{"credentials", "legacy-indexes"},
		nil,
		&stdout,
		&stderr,
	)
	if exitCode == 0 ||
		stdout.Len() != 0 ||
		!strings.Contains(
			stderr.String(),
			"could not be inspected safely",
		) ||
		strings.Contains(stderr.String(), privatePath) {
		t.Fatalf(
			"legacy command exit/stdout/stderr = %d/%q/%q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}

func writeLegacyIndex(
	t *testing.T,
	home string,
	relative string,
	content string,
	mode os.FileMode,
) {
	t.Helper()
	path := filepath.Join(home, relative)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatalf("create legacy index parent: %v", err)
	}
	if err := os.WriteFile(path, []byte(content), mode); err != nil {
		t.Fatalf("write legacy index: %v", err)
	}
}

func indexStates(states []credentialmigration.IndexState) []string {
	result := make([]string, len(states))
	for index, state := range states {
		result[index] = string(state)
	}
	return result
}

func legacyCredentialReleaseFixture() releasecontract.Release {
	fixtures := []struct {
		component domain.ComponentID
		resource  string
		root      domain.RootID
		template  string
	}{
		{
			domain.ComponentClaudeCode,
			"claude-code.credentials-index",
			domain.RootClaudeConfig,
			"claude",
		},
		{
			domain.ComponentCodex,
			"codex.credentials-index",
			domain.RootCodexConfig,
			"codex",
		},
		{
			domain.ComponentOpenCode,
			"opencode.credentials-index",
			domain.RootOpenCodeConfig,
			"opencode",
		},
		{
			domain.ComponentAntigravity2,
			"antigravity-2.credentials-index",
			domain.RootAntigravityData,
			"antigravity",
		},
	}
	release := releasecontract.Release{
		ID:          "release-a",
		IndexSHA256: strings.Repeat("a", 64),
	}
	for _, fixture := range fixtures {
		release.Resources = append(release.Resources, releasecontract.Resource{
			ID: fixture.resource, ComponentID: fixture.component,
			Strategy: releasecontract.StrategySeedIfAbsent,
			Target: domain.Location{
				Root: fixture.root, Path: "credentials-index.md",
			},
			SourceContent: []byte(fixture.template),
		})
	}
	return release
}
