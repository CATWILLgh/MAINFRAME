package tui

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

func TestCredentialReferenceOptionsAreSortedDeduplicatedAndKeepManualEntry(t *testing.T) {
	state := testCredentialState(t)
	instances, err := credentialcatalog.BuildInstances([]credentialcatalog.Instance{
		{
			ID: "context7-work", ServiceID: "context7", Name: "Work", Purpose: "Work docs",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key", Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment, Name: "CONTEXT7_HOME_KEY",
				},
			}},
		},
		{
			ID: "context7-team", ServiceID: "context7", Name: "Team", Purpose: "Team docs",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key", Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment, Name: "CONTEXT7_TEAM_KEY",
				},
			}},
		},
		{
			ID: "context7-lab", ServiceID: "context7", Name: "Lab", Purpose: "Lab docs",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key", Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment, Name: "CONTEXT7_HOME_KEY",
				},
			}},
		},
	}, state.Definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}

	options := credentialReferenceOptions(instances)
	labels := make([]string, len(options))
	for index, option := range options {
		labels[index] = option.Key
	}
	want := []string{
		"Enter a new reference name",
		"CONTEXT7_HOME_KEY — 2 credential-instance references",
		"CONTEXT7_TEAM_KEY — 1 credential-instance references",
	}
	if len(labels) != len(want) {
		t.Fatalf("option labels = %v, want %v", labels, want)
	}
	for index := range want {
		if labels[index] != want[index] {
			t.Fatalf("option label %d = %q, want %q", index, labels[index], want[index])
		}
	}

	draft := draftFromInstance(instances.All()[0])
	if draft.credentials[0].referenceChoice != "CONTEXT7_HOME_KEY" {
		t.Fatalf("edit reference choice = %q", draft.credentials[0].referenceChoice)
	}
}
