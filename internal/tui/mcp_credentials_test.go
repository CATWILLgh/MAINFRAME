package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestMCPKeyDraftIsMaskedAndExcludedFromPlans(t *testing.T) {
	const sentinel = "sensitive-value-never-render"
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := newTestModel(t, previewer)
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	choice.credentialDraft = sentinel

	model.openMCPDetail("context7")
	detail := model.View().Content
	for _, text := range []string{"Configure Context7", "Draft only"} {
		if !strings.Contains(detail, text) {
			t.Fatalf("key detail does not contain %q:\n%s", text, detail)
		}
	}
	field := credentialField(testServer(t, model.catalog, "context7"), choice)
	field.Focus()
	fieldView := field.View()
	for _, text := range []string{
		"Context7 API key", "masked", "process memory", "not stored or applied",
	} {
		if !strings.Contains(fieldView, text) {
			t.Fatalf("key field does not contain %q:\n%s", text, fieldView)
		}
	}
	if strings.Contains(detail, sentinel) || strings.Contains(fieldView, sentinel) {
		t.Fatal("key draft appeared in rendered detail output")
	}

	model.backToMCPList()
	if strings.Contains(model.View().Content, sentinel) {
		t.Fatal("key draft appeared in the MCP catalog")
	}
	if !strings.Contains(model.View().Content, "key held in memory") {
		t.Fatalf("catalog does not describe the key draft:\n%s", model.View().Content)
	}

	updated, command := model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	preview := updated.View().Content
	if strings.Contains(preview, sentinel) {
		t.Fatal("key draft appeared in the complete preview")
	}
	if !strings.Contains(preview, "API key provided for this session; not stored or applied") {
		t.Fatalf("preview does not describe the key draft:\n%s", preview)
	}
	if strings.Contains(strings.Join(selectionStrings(previewer.mcpSelections), "\n"), sentinel) {
		t.Fatal("key draft entered lifecycle selections")
	}
}

func TestMCPKeyInputCannotTriggerNavigationOrPreviousConfirmationBindings(t *testing.T) {
	const sentinel = "visible-test-key-with-b-and-q"
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCPDetail("context7")

	updated, command := model.continueFromMCPDetail()
	if updated.screen != screenMCPCredential || command == nil {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	for _, character := range sentinel {
		updatedModel, _ := updated.Update(keyPress(string(character)))
		updated = updatedModel.(*Model)
		if updated.screen != screenMCPCredential {
			t.Fatalf("character %q left the credential screen", character)
		}
		if strings.Contains(updated.View().Content, sentinel) {
			t.Fatal("key draft appeared while typing")
		}
	}
	if choice.credentialDraft != sentinel {
		t.Fatal("credential field did not retain the complete key draft")
	}
}

func TestMCPKeyDraftIsClearedWhenNoLongerRequired(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	choice.credentialDraft = "discard-this-value"
	model.openMCPDetail("context7")

	choice.ProfileID = "remote-keyless"
	model.backToMCPList()
	if choice.credentialDraft != "" {
		t.Fatal("key draft survived a switch to a keyless profile")
	}

	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.credentialDraft = "discard-this-value"
	model.selected = nil
	model.reconcileMCPChoices()
	if choice.Enabled || choice.credentialDraft != "" {
		t.Fatal("key draft survived removal of all target environments")
	}
}

func TestMCPKeyValidationRejectsOnlyBlankValuesWithoutEchoingInput(t *testing.T) {
	if err := validateCredentialDraft(" \t "); err == nil {
		t.Fatal("blank API key was accepted")
	}
	const sentinel = "sensitive-value-never-render"
	if err := validateCredentialDraft(sentinel); err != nil {
		if strings.Contains(err.Error(), sentinel) {
			t.Fatal("credential validation error echoed the key")
		}
		t.Fatalf("valid API key was rejected: %v", err)
	}
}

func TestMCPKeyStatusDoesNotClaimWhitespaceIsAvailable(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	choice.credentialDraft = "   "

	if strings.Contains(model.mcpChoiceStatus("context7"), "key held in memory") {
		t.Fatal("whitespace-only key draft was reported as available")
	}
}

func TestMCPKeyDraftIsRequiredBeforePreview(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := newTestModel(t, previewer)
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
	if !strings.Contains(updated.View().Content, "Context7: API key is required") {
		t.Fatalf("missing key error is absent:\n%s", updated.View().Content)
	}
	if previewer.calls != 0 {
		t.Fatalf("lifecycle preview calls = %d", previewer.calls)
	}
}

func TestCredentialScreenControlCQuitClearsMCPKeyDraft(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.selected = []domain.ComponentID{domain.ComponentClaudeCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentClaudeCode}
	choice.credentialDraft = "discard-on-quit"
	model.openMCPDetail("context7")
	model.continueFromMCPDetail()

	_, command := model.Update(keyPress("ctrl+c"))
	if command == nil {
		t.Fatal("quit command is missing")
	}
	if choice.credentialDraft != "" {
		t.Fatal("key draft survived quit handling")
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

func selectionStrings(selections []mcpcatalog.Selection) []string {
	result := make([]string, 0, len(selections))
	for _, selection := range selections {
		result = append(result, string(selection.ServerID), string(selection.ProfileID))
		for _, adapter := range selection.Adapters {
			result = append(result, string(adapter))
		}
	}
	return result
}
