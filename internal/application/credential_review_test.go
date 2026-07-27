package application

import (
	"io/fs"
	"os"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestReviewCombinesCredentialMutationAndMarksCredentialOnlyApply(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	credentialSnapshot, err := credentialcatalog.ObserveInstances(
		applicationCredentialHost{},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	snapshot := testSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}}
	service, err := New(
		builder,
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	desired, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{applicationCredentialInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}

	reviewed, err := service.Review(Request{CredentialInstances: &desired})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if !reviewed.CredentialOnlyApplicable() {
		t.Fatal("credential-only plan was not applicable")
	}
	changes := reviewed.CredentialChanges()
	if len(changes) != 1 ||
		changes[0].Kind != credentialcatalog.ChangeCreate {
		t.Fatalf("credential changes = %#v", changes)
	}
	changes[0].After.Credentials[0].Secret.Name = "MUTATED"
	if reviewed.CredentialChanges()[0].After.Credentials[0].Secret.Name !=
		"CONTEXT7_HOME_KEY" {
		t.Fatal("CredentialChanges() exposed mutable nested state")
	}
	transitions := reviewed.Executable().Configuration.Transitions()
	if len(transitions) != 1 ||
		transitions[0].ResourceIDs[0] != "credentials.instances" {
		t.Fatalf("configuration transitions = %#v", transitions)
	}
}

func TestReviewDoesNotMarkMixedPlanAsCredentialOnlyApply(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	credentialSnapshot, err := credentialcatalog.ObserveInstances(
		applicationCredentialHost{},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	snapshot := testSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	desired, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{applicationCredentialInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}

	reviewed, err := service.Review(Request{
		Components:          []domain.ComponentID{domain.ComponentClaudeCode},
		CredentialInstances: &desired,
	})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if reviewed.CredentialOnlyApplicable() {
		t.Fatal("mixed filesystem and credential plan was marked applicable")
	}
}

func TestApplyCredentialsRejectsMixedPlanBeforeRecovery(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	credentialSnapshot, err := credentialcatalog.ObserveInstances(
		applicationCredentialHost{},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	snapshot := testSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	recovery := &fakeRecoveryExecutorFactory{
		session: &fakeRecoverySession{},
	}
	apply := &fakeApplyExecutorFactory{session: &fakeApplySession{}}
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		apply,
		recovery,
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	desired, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{applicationCredentialInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	reviewed, err := service.Review(Request{
		Components:          []domain.ComponentID{domain.ComponentClaudeCode},
		CredentialInstances: &desired,
	})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.ApplyCredentials(reviewed); err == nil {
		t.Fatal("ApplyCredentials() accepted a mixed plan")
	}
	if recovery.opens != 0 || apply.opens != 0 {
		t.Fatalf(
			"rejected apply opened resources: recovery %d, apply %d",
			recovery.opens,
			apply.opens,
		)
	}
}

func TestReviewRequiresCredentialSnapshotForCredentialIntent(t *testing.T) {
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	definitions := applicationCredentialDefinitions(t)
	desired, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{applicationCredentialInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	if _, err := service.Review(
		Request{CredentialInstances: &desired},
	); err == nil {
		t.Fatal("Review() accepted credential intent without a snapshot")
	}
}

type applicationCredentialHost struct{}

func (applicationCredentialHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	return hostfs.Entry{}, fs.ErrNotExist
}

func applicationCredentialDefinitions(
	t *testing.T,
) credentialcatalog.Definitions {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
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

func applicationCredentialInstance() credentialcatalog.Instance {
	return credentialcatalog.Instance{
		ID: "context7-home", ServiceID: "context7",
		Name: "Home", Purpose: "Personal documentation lookup",
		Credentials: []credentialcatalog.CredentialBinding{{
			RoleID: "api-key",
			Secret: credentialcatalog.SecretReference{
				Backend: credentialcatalog.BackendSecretEnvironment,
				Name:    "CONTEXT7_HOME_KEY",
			},
		}},
	}
}
