package credentialcatalog

import (
	"io/fs"
	"os"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestResolveMCPSecretReturnsOnlyTheSelectedEnvironmentReference(t *testing.T) {
	definitions := context7Definitions(t)
	snapshot, err := ObserveInstances(missingCredentialHost{}, definitions)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	instances := context7Instances(t, definitions)

	got, err := snapshot.ResolveMCPSecret(
		instances,
		"context7",
		"remote-api-key",
		"context7-home",
	)
	if err != nil {
		t.Fatalf("ResolveMCPSecret() error = %v", err)
	}
	want := SecretReference{
		Backend: BackendSecretEnvironment,
		Name:    "CUSTOM_CONTEXT7_KEY",
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("ResolveMCPSecret() = %#v, want %#v", got, want)
	}
}

func TestResolveMCPSecretRejectsBindingOutsideTheEffectiveInstances(t *testing.T) {
	definitions := context7Definitions(t)
	snapshot, err := ObserveInstances(missingCredentialHost{}, definitions)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	instances := context7Instances(t, definitions)
	tests := []struct {
		name      string
		serverID  mcpcatalog.ServerID
		profileID mcpcatalog.ProfileID
		instance  InstanceID
	}{
		{
			name: "missing instance", serverID: "context7",
			profileID: "remote-api-key", instance: "context7-missing",
		},
		{
			name: "wrong service", serverID: "other-service",
			profileID: "remote-api-key", instance: "context7-home",
		},
		{
			name: "wrong profile", serverID: "context7",
			profileID: "remote-keyless", instance: "context7-home",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := snapshot.ResolveMCPSecret(
				instances,
				test.serverID,
				test.profileID,
				test.instance,
			); err == nil {
				t.Fatal("ResolveMCPSecret() accepted an invalid MCP binding")
			}
		})
	}
}

func context7Definitions(t *testing.T) Definitions {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	definitions, err := ParseDefinitions(BundledDefinitionsJSON(), catalog)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}
	return definitions
}

func context7Instances(t *testing.T, definitions Definitions) Instances {
	t.Helper()
	instances, err := BuildInstances([]Instance{{
		ID: "context7-home", ServiceID: "context7",
		Name: "Home", Purpose: "Documentation lookup",
		Credentials: []CredentialBinding{{
			RoleID: "api-key",
			Secret: SecretReference{
				Backend: BackendSecretEnvironment,
				Name:    "CUSTOM_CONTEXT7_KEY",
			},
		}},
	}}, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	return instances
}

type missingCredentialHost struct{}

func (missingCredentialHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	return hostfs.Entry{}, fs.ErrNotExist
}
