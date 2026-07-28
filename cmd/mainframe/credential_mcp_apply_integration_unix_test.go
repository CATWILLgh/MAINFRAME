//go:build darwin || linux

package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestApplyConfirmedManagesOpenCodePrivateCredentialFileLifecycle(t *testing.T) {
	fixture := newOpenCodeCredentialFixture(t)
	fixture.apply(fixture.keyed)
	assertCredentialMCPApplyState(
		t,
		fixture.home,
		fixture.config,
		"raw-secret-must-not-appear",
	)

	fixture.rotate("rotated-test-secret")
	fixture.apply(fixture.keyed)
	assertCredentialMCPApplyState(
		t,
		fixture.home,
		fixture.config,
		"rotated-test-secret",
	)

	fixture.apply(fixture.keyless())
	assertCredentialMCPKeylessState(t, fixture.config)

	fixture.apply(fixture.keyed)
	assertCredentialMCPApplyState(
		t,
		fixture.home,
		fixture.config,
		"rotated-test-secret",
	)

	fixture.apply(fixture.removed())
	assertCredentialMCPRemovedState(t, fixture.config)
}

func TestOpenCodePrivateCredentialRejectsPermissiveParentDirectory(t *testing.T) {
	fixture := newOpenCodeCredentialFixture(t)
	directory := filepath.Join(
		fixture.config,
		"opencode",
		"mainframe",
		"secrets",
	)
	if err := os.MkdirAll(directory, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(directory, 0o755); err != nil {
		t.Fatal(err)
	}

	reviewed, err := fixture.service.Review(fixture.keyed)
	if err == nil || reviewed.Applicable() {
		t.Fatal("permissive private credential parent was accepted")
	}
	assertCredentialMCPSecretAbsent(t, fixture.config)
}

type openCodeCredentialFixture struct {
	t               *testing.T
	home            string
	config          string
	secretValuePath string
	service         application.Service
	keyed           application.Request
}

func newOpenCodeCredentialFixture(t *testing.T) openCodeCredentialFixture {
	t.Helper()
	home := canonicalTempDir(t)
	config := canonicalTempDir(t)
	state := canonicalTempDir(t)
	releaseRoot := canonicalTempDir(t)
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", config)
	t.Setenv("XDG_STATE_HOME", state)
	secretValuePath := filepath.Join(t.TempDir(), "context7-value")
	if err := os.WriteFile(
		secretValuePath,
		[]byte("raw-secret-must-not-appear"),
		0o600,
	); err != nil {
		t.Fatal(err)
	}
	t.Setenv("MAINFRAME_TEST_SECRET_VALUE", secretValuePath)
	writeAntigravitySecretHelper(t, home)
	environment := credentialMCPEnvironment(home, config, state)
	namespace := credentialMCPNamespace(t, environment, releaseRoot)
	catalog := credentialMCPApplyCatalog(t)
	definitions := credentialLifecycleDefinitions(t)
	release := releasecontract.Release{
		ID: "credential-mcp-test", Model: previewOwnershipModel(t),
		MCPCatalog: catalog,
		MCPProjections: []releasecontract.MCPProjection{
			previewMCPProjection(),
		},
	}
	builder := refreshingCredentialMCPSnapshotBuilder{
		namespace: namespace, definitions: definitions,
		releaseRoot: releaseRoot, release: release,
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
	return openCodeCredentialFixture{
		t: t, home: home, config: config,
		secretValuePath: secretValuePath,
		service:         service, keyed: request,
	}
}

func (fixture openCodeCredentialFixture) keyless() application.Request {
	keyless := fixture.keyed
	keyless.MCPSelections = []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentOpenCode},
	}}
	keyless.MCPCredentials = nil
	return keyless
}

func (fixture openCodeCredentialFixture) removed() application.Request {
	removed := fixture.keyed
	removed.MCPSelections = nil
	removed.MCPCredentials = nil
	return removed
}

func (fixture openCodeCredentialFixture) rotate(value string) {
	fixture.t.Helper()
	if err := os.WriteFile(
		fixture.secretValuePath,
		[]byte(value),
		0o600,
	); err != nil {
		fixture.t.Fatal(err)
	}
}

func (fixture openCodeCredentialFixture) apply(request application.Request) {
	fixture.t.Helper()
	reviewed, err := fixture.service.Review(request)
	if err != nil {
		fixture.t.Fatalf("Review() error = %v", err)
	}
	if _, err := fixture.service.ApplyConfirmed(reviewed); err != nil {
		fixture.t.Fatalf("ApplyConfirmed() error = %v", err)
	}
}

type refreshingCredentialMCPSnapshotBuilder struct {
	namespace   hostfs.Namespace
	definitions credentialcatalog.Definitions
	releaseRoot string
	release     releasecontract.Release
}

func (builder refreshingCredentialMCPSnapshotBuilder) Build(
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
			IndexSHA256: applyRuntimeDigest(7),
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
	builder application.SnapshotBuilder,
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
