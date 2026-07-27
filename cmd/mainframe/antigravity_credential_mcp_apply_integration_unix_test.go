//go:build darwin || linux

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const antigravityIntegrationSecret = "test-only-context7-key"

func TestAntigravityKeyedContext7LifecycleUsesStandardConfiguration(t *testing.T) {
	fixture := newAntigravityMCPFixture(t)
	keyed := fixture.request("remote-api-key", true)

	fixture.reviewAndApply(keyed)
	fixture.assertKeyedState(antigravityIntegrationSecret)
	fixture.assertForeignAdaptersUntouched()

	before, err := os.Stat(fixture.configPath)
	if err != nil {
		t.Fatal(err)
	}
	fixture.reviewAndApply(keyed)
	after, err := os.Stat(fixture.configPath)
	if err != nil {
		t.Fatal(err)
	}
	if !os.SameFile(before, after) {
		t.Fatal("unchanged keyed configuration was rewritten")
	}

	rotated := "test-only-context7-key-rotated"
	if err := os.WriteFile(fixture.secretValuePath, []byte(rotated), 0o600); err != nil {
		t.Fatal(err)
	}
	fixture.reviewAndApply(keyed)
	fixture.assertKeyedState(rotated)

	fixture.reviewAndApply(fixture.request("remote-keyless", false))
	fixture.assertKeylessState()

	fixture.reviewAndApply(fixture.request("", false))
	fixture.assertRemovedState()
	fixture.assertForeignAdaptersUntouched()
}

type antigravityMCPFixture struct {
	t               *testing.T
	service         application.Service
	instances       credentialcatalog.Instances
	namespace       hostfs.Namespace
	configPath      string
	registryPath    string
	secretValuePath string
}

func newAntigravityMCPFixture(t *testing.T) antigravityMCPFixture {
	t.Helper()
	home := canonicalTempDir(t)
	config := canonicalTempDir(t)
	state := canonicalTempDir(t)
	releaseRoot := canonicalTempDir(t)
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", config)
	t.Setenv("XDG_STATE_HOME", state)
	service, namespace, definitions := newAntigravityMCPService(
		t,
		home,
		config,
		state,
		releaseRoot,
	)
	secretValuePath := filepath.Join(t.TempDir(), "context7-value")
	if err := os.WriteFile(
		secretValuePath,
		[]byte(antigravityIntegrationSecret),
		0o600,
	); err != nil {
		t.Fatal(err)
	}
	t.Setenv("MAINFRAME_TEST_SECRET_VALUE", secretValuePath)
	writeAntigravitySecretHelper(t, home)
	desired := credentialLifecycleInstances(
		t, definitions, "Home", "CONTEXT7_HOME_KEY",
	)
	return antigravityMCPFixture{
		t: t, service: service, instances: desired, namespace: namespace,
		configPath: filepath.Join(
			home, ".gemini", "config", "mcp_config.json",
		),
		registryPath: filepath.Join(
			home, ".gemini", "antigravity", "mainframe", "mcp-ownership.json",
		),
		secretValuePath: secretValuePath,
	}
}

func newAntigravityMCPService(
	t *testing.T,
	home string,
	config string,
	state string,
	releaseRoot string,
) (application.Service, hostfs.Namespace, credentialcatalog.Definitions) {
	t.Helper()
	environment := credentialMCPEnvironment(home, config, state)
	namespace := credentialMCPNamespace(t, environment, releaseRoot)
	catalog := credentialMCPApplyCatalog(t)
	definitions := credentialLifecycleDefinitions(t)
	release := releasecontract.Release{
		ID:    "antigravity-credential-mcp-test",
		Model: previewOwnershipModel(t), MCPCatalog: catalog,
		MCPProjections: []releasecontract.MCPProjection{
			antigravityIntegrationProjection(),
		},
	}
	builder := antigravityMCPSnapshotBuilder{
		releaseRoot: releaseRoot,
		release:     release,
		namespace:   namespace,
		definitions: definitions,
	}
	return credentialMCPApplyService(
		t, builder, environment, releaseRoot,
	), namespace, definitions
}

type antigravityMCPSnapshotBuilder struct {
	releaseRoot string
	release     releasecontract.Release
	namespace   hostfs.Namespace
	definitions credentialcatalog.Definitions
}

func (builder antigravityMCPSnapshotBuilder) Build(
	request application.Request,
) (application.Snapshot, error) {
	lifecycleService, err := buildPreviewServiceFrom(
		builder.releaseRoot,
		builder.release,
	)
	if err != nil {
		return application.Snapshot{}, err
	}
	snapshot := application.Snapshot{
		Release: executor.ReleaseIdentity{
			ID:          builder.release.ID,
			IndexSHA256: applyRuntimeDigest(9),
		},
		Lifecycle: lifecycleService,
	}
	if request.CredentialInstances != nil || len(request.MCPCredentials) > 0 {
		credentials, observeErr := credentialcatalog.ObserveInstances(
			builder.namespace,
			builder.definitions,
		)
		if observeErr != nil {
			return application.Snapshot{}, observeErr
		}
		snapshot.Credentials = &credentials
	}
	return snapshot, nil
}

func (fixture antigravityMCPFixture) request(
	profile mcpcatalog.ProfileID,
	keyed bool,
) application.Request {
	request := application.Request{
		Components: []domain.ComponentID{domain.ComponentAntigravity2},
	}
	if profile == "" {
		return request
	}
	request.MCPSelections = []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: profile,
		Adapters: []domain.ComponentID{domain.ComponentAntigravity2},
	}}
	if keyed {
		request.MCPCredentials = []application.MCPCredentialBinding{{
			ServerID: "context7", ProfileID: profile,
			InstanceID: "context7-home",
		}}
		desired := fixture.instances
		request.CredentialInstances = &desired
	}
	return request
}

func (fixture antigravityMCPFixture) reviewAndApply(request application.Request) {
	fixture.t.Helper()
	reviewed, err := fixture.service.Review(request)
	if err != nil {
		fixture.t.Fatalf("Review() error = %v", err)
	}
	for _, transition := range reviewed.Executable().Configuration.Transitions() {
		for _, mutation := range transition.Mutations {
			if strings.Contains(
				string(mutation.After.Content),
				antigravityIntegrationSecret,
			) {
				fixture.t.Fatal("review contains the resolved secret")
			}
			if mutation.Target.Root == domain.RootAntigravityConfig &&
				mutation.Before.Exists {
				entry, inspectErr := fixture.namespace.Inspect(
					mutation.Target,
					true,
				)
				if inspectErr != nil {
					fixture.t.Fatal(inspectErr)
				}
				digest := sha256.Sum256(entry.Content)
				if hex.EncodeToString(digest[:]) != mutation.Before.SHA256 ||
					entry.Mode != mutation.Before.Mode ||
					entry.Device != mutation.Before.Device ||
					entry.Inode != mutation.Before.Inode ||
					entry.BirthSeconds != mutation.Before.BirthSeconds ||
					entry.BirthNanoseconds != mutation.Before.BirthNanoseconds {
					fixture.t.Fatal(
						"reviewed before-image identity does not match the configuration",
					)
				}
			}
		}
	}
	if _, err := fixture.service.ApplyConfirmed(reviewed); err != nil {
		fixture.t.Fatalf("ApplyConfirmed() error = %v", err)
	}
}

func (fixture antigravityMCPFixture) assertKeyedState(secret string) {
	fixture.t.Helper()
	config := readJSONObject(fixture.t, fixture.configPath, 0o600)
	servers := config["mcpServers"].(map[string]any)
	context7 := servers["context7"].(map[string]any)
	headers := context7["headers"].(map[string]any)
	if headers["CONTEXT7_API_KEY"] != secret {
		fixture.t.Fatal("Antigravity did not receive the selected key")
	}
	registryPayload, err := os.ReadFile(fixture.registryPath)
	if err != nil {
		fixture.t.Fatal(err)
	}
	if strings.Contains(string(registryPayload), secret) {
		fixture.t.Fatal("ownership registry contains the resolved secret")
	}
	registry := readJSONObject(fixture.t, fixture.registryPath, 0o600)
	owned := registry["servers"].(map[string]any)["context7"].(map[string]any)
	digest := sha256.Sum256(canonicalJSON(fixture.t, context7))
	if owned["entry_sha256"] != hex.EncodeToString(digest[:]) ||
		owned["secret_reference"] != "CONTEXT7_HOME_KEY" {
		fixture.t.Fatal("ownership registry does not describe the managed entry")
	}
}

func (fixture antigravityMCPFixture) assertKeylessState() {
	fixture.t.Helper()
	config := readJSONObject(fixture.t, fixture.configPath, 0o600)
	context7 := config["mcpServers"].(map[string]any)["context7"].(map[string]any)
	if _, exists := context7["headers"]; exists {
		fixture.t.Fatal("keyless Context7 retained keyed headers")
	}
}

func (fixture antigravityMCPFixture) assertRemovedState() {
	fixture.t.Helper()
	config := readJSONObject(fixture.t, fixture.configPath, 0o600)
	if _, exists := config["mcpServers"].(map[string]any)["context7"]; exists {
		fixture.t.Fatal("deselection retained the managed Context7 entry")
	}
}

func (fixture antigravityMCPFixture) assertForeignAdaptersUntouched() {
	fixture.t.Helper()
	home := filepath.Dir(filepath.Dir(filepath.Dir(fixture.configPath)))
	for _, path := range []string{
		filepath.Join(home, ".claude"),
		filepath.Join(home, ".codex"),
	} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			fixture.t.Fatalf("unselected adapter root exists: %s", path)
		}
	}
}

func antigravityIntegrationProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID:          "antigravity-2.mcp.context7",
		ComponentID: domain.ComponentAntigravity2,
		Codec:       releasecontract.MCPProjectionAntigravityGlobalHTTP,
		ServerID:    "context7",
		ProfileID:   "remote-keyless",
		Target: domain.Location{
			Root: domain.RootAntigravityConfig, Path: "mcp_config.json",
		},
		MapPointer: "/mcpServers", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootAntigravityData,
			Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"serverUrl":"https://mcp.context7.com/mcp"}`,
	}
}

func writeAntigravitySecretHelper(t *testing.T, home string) {
	t.Helper()
	path := filepath.Join(home, ".local", "bin", "secret")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	payload := []byte(
		"#!/bin/sh\n" +
			"set -eu\n" +
			"test \"$1\" = get\n" +
			"test \"$2\" = CONTEXT7_HOME_KEY\n" +
			"exec /bin/cat \"$MAINFRAME_TEST_SECRET_VALUE\"\n",
	)
	if err := os.WriteFile(path, payload, 0o700); err != nil {
		t.Fatal(err)
	}
}

func readJSONObject(t *testing.T, path string, mode os.FileMode) map[string]any {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != mode {
		t.Fatalf("mode = %#o, want %#o", info.Mode().Perm(), mode)
	}
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var result map[string]any
	if err := json.Unmarshal(payload, &result); err != nil {
		t.Fatalf("decode JSON: %v", err)
	}
	return result
}

func canonicalJSON(t *testing.T, value any) []byte {
	t.Helper()
	payload, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return payload
}
