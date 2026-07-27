package credentialcatalog

import (
	"bytes"
	"testing"
)

func TestCreateInstanceNormalizesAndRoundTripsDocument(t *testing.T) {
	definitions := testDefinitions(t)
	current, err := BuildInstances(nil, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}

	updated, change, err := CreateInstance(current, Instance{
		ID:        "dokploy-staging",
		ServiceID: "dokploy",
		Name:      "Work",
		Purpose:   "Company documentation lookup",
		Credentials: []CredentialBinding{{
			RoleID: "api-key",
			Secret: SecretReference{
				Backend: BackendSecretEnvironment,
				Name:    "DOKPLOY_STAGING_KEY",
			},
		}},
	}, definitions)
	if err != nil {
		t.Fatalf("CreateInstance() error = %v", err)
	}
	if change.Kind != ChangeCreate || change.After.ID != "dokploy-staging" {
		t.Fatalf("change = %#v", change)
	}

	payload, err := EncodeInstances(updated)
	if err != nil {
		t.Fatalf("EncodeInstances() error = %v", err)
	}
	if bytes.Contains(payload, []byte("secret-value")) {
		t.Fatal("encoded metadata unexpectedly contains a secret value")
	}
	parsed, err := ParseInstances(payload, definitions)
	if err != nil {
		t.Fatalf("ParseInstances(encoded) error = %v", err)
	}
	if got := parsed.All(); len(got) != 1 ||
		got[0].Credentials[0].Secret.Name != "DOKPLOY_STAGING_KEY" {
		t.Fatalf("round trip = %#v", got)
	}
}

func TestEditInstancePreservesIdentityServiceAndRequirements(t *testing.T) {
	definitions := testDefinitions(t)
	current, err := ParseInstances(distinctInstancesPayload(), definitions)
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}
	before := current.ForService("dokploy")[0]
	replacement := before
	replacement.Name = "Home production"
	replacement.Purpose = "Personal production deployments"
	replacement.Credentials[0].Secret.Name = "DOKPLOY_HOME_ADMIN_V2"

	updated, change, err := EditInstance(
		current,
		before.ID,
		replacement,
		definitions,
	)
	if err != nil {
		t.Fatalf("EditInstance() error = %v", err)
	}
	if change.Kind != ChangeUpdate ||
		len(change.After.Credentials[1].Requirements) != 1 {
		t.Fatalf("change = %#v", change)
	}
	got := updated.ForService("dokploy")[0]
	if got.Name != replacement.Name ||
		got.Credentials[1].Requirements[0] != before.Credentials[1].Requirements[0] {
		t.Fatalf("updated instance = %#v", got)
	}

	replacement.ID = "renamed"
	if _, _, err := EditInstance(current, before.ID, replacement, definitions); err == nil {
		t.Fatal("EditInstance() accepted an identity change")
	}
	replacement = before
	replacement.ServiceID = "context7"
	if _, _, err := EditInstance(current, before.ID, replacement, definitions); err == nil {
		t.Fatal("EditInstance() accepted a service change")
	}
}

func TestInstanceLifecycleRejectsDuplicatesUnknownsAndInvalidReferences(t *testing.T) {
	definitions := testDefinitions(t)
	current, err := BuildInstances(nil, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	valid := Instance{
		ID: "dokploy-home", ServiceID: "dokploy",
		Name: "Home", Purpose: "Personal documentation lookup",
		Credentials: []CredentialBinding{{
			RoleID: "api-key",
			Secret: SecretReference{
				Backend: BackendSecretEnvironment,
				Name:    "DOKPLOY_HOME_KEY",
			},
		}},
	}
	current, _, err = CreateInstance(current, valid, definitions)
	if err != nil {
		t.Fatalf("CreateInstance() error = %v", err)
	}
	if _, _, err := CreateInstance(current, valid, definitions); err == nil {
		t.Fatal("CreateInstance() accepted a duplicate id")
	}
	valid.ServiceID = "unknown"
	valid.ID = "unknown-service"
	if _, _, err := CreateInstance(current, valid, definitions); err == nil {
		t.Fatal("CreateInstance() accepted an unknown service")
	}
	valid.ServiceID = "dokploy"
	valid.ID = "invalid-reference"
	valid.Credentials[0].Secret.Name = "not shell safe"
	if _, _, err := CreateInstance(current, valid, definitions); err == nil {
		t.Fatal("CreateInstance() accepted an invalid secret reference")
	}
}

func TestPlanInstanceChangesRejectsImplicitDeletion(t *testing.T) {
	definitions := testDefinitions(t)
	current, err := ParseInstances(distinctInstancesPayload(), definitions)
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}
	desired, err := BuildInstances(current.All()[1:], definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	if _, err := PlanInstanceChanges(current, desired); err == nil {
		t.Fatal("PlanInstanceChanges() accepted an implicit deletion")
	}
}
