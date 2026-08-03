//go:build darwin || linux

package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestCredentialLifecycleCreatesPrivatelyAndPreservesConcurrentEdit(
	t *testing.T,
) {
	fixture := newCredentialLifecycleFixture(t)
	desired := credentialLifecycleInstances(
		t,
		fixture.definitions,
		"Home",
		"CONTEXT7_HOME_KEY",
	)
	reviewed, err := fixture.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		t.Fatalf("Review(create) error = %v", err)
	}
	if _, err := fixture.service.ApplyCredentials(reviewed); err != nil {
		t.Fatalf("ApplyCredentials(create) error = %v", err)
	}
	payload, err := os.ReadFile(fixture.instancesPath)
	if err != nil {
		t.Fatalf("read created instances: %v", err)
	}
	if _, err := credentialcatalog.ParseInstances(
		payload,
		fixture.definitions,
	); err != nil {
		t.Fatalf("created instances are invalid: %v", err)
	}
	info, err := os.Stat(fixture.instancesPath)
	if err != nil {
		t.Fatalf("stat created instances: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("instances mode = %#o", info.Mode().Perm())
	}
	parentInfo, err := os.Stat(filepath.Dir(fixture.instancesPath))
	if err != nil {
		t.Fatalf("stat instances parent: %v", err)
	}
	if parentInfo.Mode().Perm() != 0o700 {
		t.Fatalf("instances parent mode = %#o", parentInfo.Mode().Perm())
	}

	edited := credentialLifecycleInstances(
		t,
		fixture.definitions,
		"Home updated",
		"CONTEXT7_HOME_KEY_V2",
	)
	reviewed, err = fixture.service.Review(application.Request{
		CredentialInstances: &edited,
	})
	if err != nil {
		t.Fatalf("Review(edit) error = %v", err)
	}
	concurrent := credentialLifecycleInstances(
		t,
		fixture.definitions,
		"Concurrent owner",
		"CONTEXT7_CONCURRENT_KEY",
	)
	concurrentPayload, err := credentialcatalog.EncodeInstances(concurrent)
	if err != nil {
		t.Fatalf("EncodeInstances(concurrent) error = %v", err)
	}
	if err := os.WriteFile(
		fixture.instancesPath,
		concurrentPayload,
		0o600,
	); err != nil {
		t.Fatalf("write concurrent edit: %v", err)
	}

	if _, err := fixture.service.ApplyCredentials(reviewed); err == nil {
		t.Fatal("ApplyCredentials(edit) ignored concurrent metadata drift")
	}
	after, err := os.ReadFile(fixture.instancesPath)
	if err != nil {
		t.Fatalf("read instances after rejected edit: %v", err)
	}
	if !bytes.Equal(after, concurrentPayload) {
		t.Fatal("rejected edit changed the concurrent owner document")
	}
}

type credentialLifecycleFixture struct {
	service       application.Service
	definitions   credentialcatalog.Definitions
	instancesPath string
	layout        hostlayout.Layout
	stateRoot     string
}

func newCredentialLifecycleFixture(
	t *testing.T,
) credentialLifecycleFixture {
	return newCredentialLifecycleFixtureWithDecorators(t, nil, nil)
}

func newCredentialLifecycleFixtureWithDecorators(
	t *testing.T,
	decorateConfigurations configurationWorkspaceDecorator,
	decorateState applyStateDecorator,
) credentialLifecycleFixture {
	t.Helper()
	home := canonicalTempDir(t)
	config := canonicalTempDir(t)
	stateBase := canonicalTempDir(t)
	releaseRoot := canonicalTempDir(t)
	environment := hostlayout.Environment{
		LookupEnv: func(name string) (string, bool) {
			switch name {
			case "XDG_CONFIG_HOME":
				return config, true
			case "XDG_STATE_HOME":
				return stateBase, true
			default:
				return "", false
			}
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "darwin",
	}
	layout, err := hostlayout.Resolve(environment, releaseRoot)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("hostfs.Open() error = %v", err)
	}
	definitions := credentialLifecycleDefinitions(t)
	lifecycleService, err := lifecycle.New(
		previewOwnershipModel(t),
		domain.ObservedState{},
	)
	if err != nil {
		t.Fatalf("lifecycle.New() error = %v", err)
	}
	builder := credentialLifecycleSnapshotBuilder{
		namespace: namespace, definitions: definitions,
		lifecycle: lifecycleService,
	}
	recoveryLayout, err := hostlayout.ResolveRecovery(environment)
	if err != nil {
		t.Fatalf("ResolveRecovery() error = %v", err)
	}
	service, err := application.New(
		builder,
		productionApplyExecutorFactory{
			resolveRoot:            func() (string, error) { return releaseRoot, nil },
			environment:            environment,
			decorateConfigurations: decorateConfigurations,
			decorateState:          decorateState,
		},
		productionRecoveryExecutorFactory{layout: recoveryLayout},
	)
	if err != nil {
		t.Fatalf("application.New() error = %v", err)
	}
	return credentialLifecycleFixture{
		service: service, definitions: definitions, layout: layout,
		stateRoot: recoveryLayout.State(),
		instancesPath: filepath.Join(
			config,
			"credentials",
			credentialcatalog.UserInstancesPath,
		),
	}
}

type credentialLifecycleSnapshotBuilder struct {
	namespace   hostfs.Namespace
	definitions credentialcatalog.Definitions
	lifecycle   lifecycle.Service
}

func (builder credentialLifecycleSnapshotBuilder) Build(
	request application.Request,
) (application.Snapshot, error) {
	snapshot := application.Snapshot{
		Release: executor.ReleaseIdentity{
			ID:          "credential-test",
			IndexSHA256: applyRuntimeDigest(7),
		},
		Lifecycle: builder.lifecycle,
	}
	if request.CredentialInstances != nil || len(request.MCPCredentials) > 0 {
		credentials, err := credentialcatalog.ObserveInstances(
			builder.namespace,
			builder.definitions,
		)
		if err != nil {
			return application.Snapshot{}, err
		}
		snapshot.Credentials = &credentials
	}
	return snapshot, nil
}

func credentialLifecycleDefinitions(
	t *testing.T,
) credentialcatalog.Definitions {
	t.Helper()
	payload, err := os.ReadFile("../../internal/mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		catalog,
	)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}
	return definitions
}

func credentialLifecycleInstances(
	t *testing.T,
	definitions credentialcatalog.Definitions,
	name string,
	reference string,
) credentialcatalog.Instances {
	t.Helper()
	instances, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{{
			ID: "context7-home", ServiceID: "context7",
			Name: name, Purpose: "Personal documentation lookup",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key",
				Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment,
					Name:    reference,
				},
			}},
		}},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	return instances
}
