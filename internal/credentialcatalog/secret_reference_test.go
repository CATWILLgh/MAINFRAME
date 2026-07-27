package credentialcatalog

import (
	"reflect"
	"testing"
)

func TestInstancesUsesReportsEveryConsumerOfSharedSecretInCatalogOrder(t *testing.T) {
	definitions := testDefinitions(t)
	instances, err := ParseInstances([]byte(`{
		"schema_version": 1,
		"kind": "mainframe-credential-instances",
		"instances": [
			{
				"id": "dokploy-home",
				"service_id": "dokploy",
				"name": "Home",
				"purpose": "Personal deployments",
				"credentials": [
					{"role_id": "admin-login", "secret": {"backend": "secret-env", "name": "DOKPLOY_SHARED"}},
					{"role_id": "api-key", "secret": {"backend": "secret-env", "name": "DOKPLOY_HOME_API"}}
				]
			},
			{
				"id": "dokploy-work",
				"service_id": "dokploy",
				"name": "Work",
				"purpose": "Company deployments",
				"credentials": [
					{"role_id": "api-key", "secret": {"backend": "secret-env", "name": "DOKPLOY_SHARED"}}
				]
			}
		]
	}`), definitions)
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}

	got := instances.Uses(SecretReference{
		Backend: BackendSecretEnvironment,
		Name:    "DOKPLOY_SHARED",
	})
	want := []SecretUse{
		{
			InstanceID: "dokploy-home", ServiceID: "dokploy",
			InstanceName: "Home", RoleID: "admin-login",
		},
		{
			InstanceID: "dokploy-work", ServiceID: "dokploy",
			InstanceName: "Work", RoleID: "api-key",
		},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Instances.Uses() = %#v, want %#v", got, want)
	}
}

func TestValidateSecretReference(t *testing.T) {
	valid := SecretReference{
		Backend: BackendSecretEnvironment,
		Name:    "DOKPLOY_SHARED",
	}
	if err := ValidateSecretReference(valid); err != nil {
		t.Fatalf("ValidateSecretReference(valid) error = %v", err)
	}

	invalid := valid
	invalid.Name = "literal-value"
	if err := ValidateSecretReference(invalid); err == nil {
		t.Fatal("ValidateSecretReference(invalid) error = nil, want validation error")
	}
}
