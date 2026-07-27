//go:build darwin || linux

package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestApplyConfirmedCreatesKeyedOpenCodeAndCredentialStateTogether(t *testing.T) {
	home := canonicalTempDir(t)
	config := canonicalTempDir(t)
	state := canonicalTempDir(t)
	releaseRoot := canonicalTempDir(t)
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", config)
	t.Setenv("XDG_STATE_HOME", state)
	t.Setenv("CONTEXT7_HOME_KEY", "raw-secret-must-not-appear")
	environment := credentialMCPEnvironment(home, config, state)
	namespace := credentialMCPNamespace(t, environment, releaseRoot)
	catalog := credentialMCPApplyCatalog(t)
	definitions := credentialLifecycleDefinitions(t)
	lifecycleService, err := buildPreviewServiceFrom(
		releaseRoot,
		releasecontract.Release{
			ID: "credential-mcp-test", Model: previewOwnershipModel(t),
			MCPCatalog: catalog,
			MCPProjections: []releasecontract.MCPProjection{
				previewMCPProjection(),
			},
		},
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	builder := credentialLifecycleSnapshotBuilder{
		namespace: namespace, definitions: definitions,
		lifecycle: lifecycleService,
	}
	service := credentialMCPApplyService(t, builder, environment, releaseRoot)
	desired := credentialLifecycleInstances(
		t, definitions, "Home", "CONTEXT7_HOME_KEY",
	)
	request := application.Request{
		Components: []domain.ComponentID{domain.ComponentOpenCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		}},
		MCPCredentials: []application.MCPCredentialBinding{{
			ServerID: "context7", ProfileID: "remote-api-key",
			InstanceID: "context7-home",
		}},
		CredentialInstances: &desired,
	}

	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if _, err := service.ApplyConfirmed(reviewed); err != nil {
		t.Fatalf("ApplyConfirmed() error = %v", err)
	}
	assertCredentialMCPApplyState(t, home, config)
}

func credentialMCPNamespace(
	t *testing.T,
	environment hostlayout.Environment,
	releaseRoot string,
) hostfs.Namespace {
	t.Helper()
	layout, err := hostlayout.Resolve(environment, releaseRoot)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("hostfs.Open() error = %v", err)
	}
	return namespace
}

func credentialMCPApplyService(
	t *testing.T,
	builder credentialLifecycleSnapshotBuilder,
	environment hostlayout.Environment,
	releaseRoot string,
) application.Service {
	t.Helper()
	recovery, err := hostlayout.ResolveRecovery(environment)
	if err != nil {
		t.Fatalf("ResolveRecovery() error = %v", err)
	}
	service, err := application.New(
		builder,
		productionApplyExecutorFactory{
			resolveRoot: func() (string, error) { return releaseRoot, nil },
			environment: environment,
		},
		productionRecoveryExecutorFactory{layout: recovery},
	)
	if err != nil {
		t.Fatalf("application.New() error = %v", err)
	}
	return service
}

func credentialMCPEnvironment(
	home string,
	config string,
	state string,
) hostlayout.Environment {
	values := map[string]string{
		"XDG_CONFIG_HOME": config,
		"XDG_STATE_HOME":  state,
	}
	return hostlayout.Environment{
		LookupEnv: func(name string) (string, bool) {
			value, exists := values[name]
			return value, exists
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "darwin",
	}
}

func credentialMCPApplyCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../../internal/mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	return catalog
}

func assertCredentialMCPApplyState(t *testing.T, home string, config string) {
	t.Helper()
	instances := filepath.Join(
		config,
		"credentials",
		"mainframe",
		"instances.json",
	)
	info, err := os.Stat(instances)
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("credential state = %#v, %v", info, err)
	}
	openCodePath := filepath.Join(config, "opencode", "opencode.json")
	payload, err := os.ReadFile(openCodePath)
	if err != nil {
		t.Fatalf("read OpenCode config: %v", err)
	}
	content := string(payload)
	if !strings.Contains(content, "{env:CONTEXT7_HOME_KEY}") ||
		strings.Contains(content, "raw-secret-must-not-appear") {
		t.Fatalf("OpenCode credential projection = %s", content)
	}
	for _, path := range []string{
		filepath.Join(home, ".claude"),
		filepath.Join(home, ".codex"),
	} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("unselected config root exists: %s (%v)", path, err)
		}
	}
}
