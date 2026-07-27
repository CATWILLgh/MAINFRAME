package tui

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestMCPCredentialScreenSelectsMetadataWithoutAcceptingValues(t *testing.T) {
	state := testCredentialState(t)
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}

	updated, command := model.openMCPCredential("context7")
	if command == nil || updated.screen != screenMCPCredential {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	view := updated.View().Content
	for _, text := range []string{
		"Context7 credential instance",
		"never reads the key value",
		"Reference only",
		"context7-home",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("credential view does not contain %q:\n%s", text, view)
		}
	}
	if strings.Contains(view, "masked") ||
		strings.Contains(view, "process memory") {
		t.Fatalf("credential view still describes raw-key input:\n%s", view)
	}
}

func TestMCPPreviewRequiresMatchingCredentialInstance(t *testing.T) {
	state := testCredentialState(t)
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := NewModel(previewer, testCatalog(t), nil, state)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}

	updated, command := model.openPreview()
	if updated.screen != screenMCP || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !strings.Contains(
		updated.View().Content,
		"Context7: create and select a credential service instance",
	) {
		t.Fatalf("missing instance error is absent:\n%s", updated.View().Content)
	}
	if previewer.calls != 0 {
		t.Fatalf("review calls = %d", previewer.calls)
	}

	choice.credentialInstanceID = "context7-home"
	updated, command = model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !strings.Contains(
		updated.View().Content,
		"Credential instance selected; secret value remains external",
	) {
		t.Fatalf("selected instance status is absent:\n%s", updated.View().Content)
	}
}

func TestMCPCredentialReferenceClearsWhenProfileNoLongerNeedsIt(t *testing.T) {
	state := testCredentialState(t)
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	choice.credentialInstanceID = "context7-home"

	choice.ProfileID = "remote-keyless"
	normalizeMCPChoice(testServer(t, model.catalog, "context7"), choice)
	if choice.credentialInstanceID != "" {
		t.Fatal("credential instance survived a switch to a keyless profile")
	}

	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.credentialInstanceID = "context7-home"
	model.selected = nil
	model.reconcileMCPChoices()
	if choice.Enabled || choice.credentialInstanceID != "" {
		t.Fatal("credential instance survived removal of all target environments")
	}
}

func testServer(
	t *testing.T,
	catalog mcpcatalog.Catalog,
	serverID mcpcatalog.ServerID,
) mcpcatalog.Server {
	t.Helper()
	server, exists := catalog.Server(serverID)
	if !exists {
		t.Fatalf("missing MCP server %q", serverID)
	}
	return server
}

func testCredentialState(t *testing.T) CredentialState {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	mcp, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		mcp,
	)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}
	instances, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{{
			ID: "context7-home", ServiceID: "context7",
			Name: "Home", Purpose: "Personal documentation lookup",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key",
				Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment,
					Name:    "CONTEXT7_HOME_KEY",
				},
			}},
		}},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	return CredentialState{Definitions: definitions, Instances: instances}
}
