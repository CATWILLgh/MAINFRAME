package application

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestOpenCodeContext7ApplicabilityAllowsExactManagedSecretsStore(
	t *testing.T,
) {
	request, semantic := context7ManagedStoreFixture()
	prepared, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{"credential-tools.secrets-store"},
		Mutations: []configuration.FileMutation{
			managedStoreMutation(
				domain.RootCredentialsConfig,
				"mainframe/file-ownership.json",
			),
			managedStoreMutation(domain.RootCredentialsConfig, "secrets.env"),
		},
	}})
	if err != nil {
		t.Fatal(err)
	}
	executable := executor.Preview{
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: domain.ComponentOpenCode,
			Kind:        domain.OperationInstall,
		}}},
		Configuration: prepared,
	}
	if !context7Applicable(request, semantic, executable) {
		t.Fatal("exact managed secrets-store transition was inapplicable")
	}
}

func TestOpenCodeContext7ApplicabilityRejectsForgedManagedStoreScope(
	t *testing.T,
) {
	request, semantic := context7ManagedStoreFixture()
	tests := map[string]configuration.Transition{
		"foreign resource": {
			ResourceIDs: []string{"credential-tools.foreign"},
			Mutations: []configuration.FileMutation{
				managedStoreMutation(domain.RootCredentialsConfig, "secrets.env"),
			},
		},
		"foreign target": {
			ResourceIDs: []string{"credential-tools.secrets-store"},
			Mutations: []configuration.FileMutation{
				managedStoreMutation(domain.RootCredentialsConfig, "foreign.env"),
			},
		},
		"registry without target": {
			ResourceIDs: []string{"credential-tools.secrets-store"},
			Mutations: []configuration.FileMutation{
				managedStoreMutation(
					domain.RootCredentialsConfig,
					"mainframe/file-ownership.json",
				),
			},
		},
		"removal during add": {
			ResourceIDs: []string{"credential-tools.secrets-store"},
			Mutations: []configuration.FileMutation{{
				Disposition: configuration.MutationRemoveManagedSecret,
				Target: domain.Location{
					Root: domain.RootCredentialsConfig,
					Path: "secrets.env",
				},
				Before: configuration.BeforeImage{
					Exists: true, SHA256: strings.Repeat("a", 64),
					Mode: 0o600, Device: 1, Inode: 2, BirthSeconds: 3,
				},
			}},
		},
	}
	for name, transition := range tests {
		t.Run(name, func(t *testing.T) {
			prepared, err := configuration.NewPreparedPlan(
				[]configuration.Transition{transition},
			)
			if err != nil {
				t.Fatal(err)
			}
			executable := executor.Preview{
				Plan: domain.Plan{Operations: []domain.Operation{{
					ComponentID: domain.ComponentOpenCode,
					Kind:        domain.OperationInstall,
				}}},
				Configuration: prepared,
			}
			if context7Applicable(request, semantic, executable) {
				t.Fatal("forged managed store scope was applicable")
			}
		})
	}
}

func TestContext7ApplicabilityRejectsForgedCredentialInstanceTransition(
	t *testing.T,
) {
	request, _ := context7ManagedStoreFixture()
	desired := applicationCredentialInstances(
		t,
		applicationCredentialDefinitions(t),
	)
	request.CredentialInstances = &desired
	transition := configuration.Transition{
		ResourceIDs: []string{"credentials.instances"},
		Mutations: []configuration.FileMutation{
			managedStoreMutation(
				domain.RootCredentialsConfig,
				"mainframe/forged-instances.json",
			),
		},
	}
	if credentialTransitionAllowed(
		domain.ComponentOpenCode,
		request,
		transition,
		"",
		false,
	) {
		t.Fatal("forged credential instance transition was allowed")
	}
}

func context7ManagedStoreFixture() (Request, lifecycle.Preview) {
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentOpenCode}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}
	semantic := lifecycle.Preview{
		Configuration: configuration.Plan{
			Changes: []configuration.Change{{
				ResourceID:  "credential-tools.secrets-store",
				ComponentID: "credential-tools",
				Kind:        configuration.ChangeAdd,
			}},
		},
		MCP: mcpconfiguration.Plan{Intents: []mcpconfiguration.Intent{{
			ComponentID: domain.ComponentOpenCode,
			ServerID:    "context7",
		}}},
	}
	return request, semantic
}

func managedStoreMutation(
	root domain.RootID,
	path domain.ArtifactPath,
) configuration.FileMutation {
	return configuration.FileMutation{
		Disposition: configuration.MutationPresent,
		Target:      domain.Location{Root: root, Path: path},
		After: configuration.AfterImage{
			Exists: true, Content: []byte("{}\n"), Mode: 0o600,
		},
	}
}
