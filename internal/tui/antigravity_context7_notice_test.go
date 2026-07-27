package tui

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const expectedAntigravityContext7Notice = "Antigravity uses its standard configuration storage for this connection because it does not support a secret reference in remote MCP headers."

func TestAntigravityContext7KeyedNoticeAppearsInReviewAndConfirmation(t *testing.T) {
	state := testCredentialState(t)
	reviewer := &credentialTUIReviewer{
		plan: credentialTUIPlan{applicable: true},
	}
	model := NewModel(reviewer, antigravityKeyedTestCatalog(t), nil, state)
	configureContext7Choice(
		model,
		"remote-api-key",
		domain.ComponentAntigravity2,
	)

	model.openMCPDetail("context7")
	if strings.Contains(model.View().Content, expectedAntigravityContext7Notice) {
		t.Fatal("configuration detail shows the review-only storage notice")
	}

	preview, command := model.openPreview()
	if command != nil || preview.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", preview.screen, command)
	}
	assertNoticeAndSafeMetadata(t, preview.View().Content)

	next, command := preview.updatePreview(keyPress("a"))
	confirmation := next.(*Model)
	if command == nil || confirmation.screen != screenApplyConfirm {
		t.Fatalf(
			"confirmation screen = %v, command = %v",
			confirmation.screen,
			command,
		)
	}
	assertNoticeAndSafeMetadata(t, confirmation.View().Content)
}

func TestAntigravityContext7KeyedNoticeIsHiddenForUnrelatedChoices(t *testing.T) {
	tests := []struct {
		name     string
		profile  mcpcatalog.ProfileID
		adapters []domain.ComponentID
	}{
		{
			name:     "keyless Antigravity",
			profile:  "remote-keyless",
			adapters: []domain.ComponentID{domain.ComponentAntigravity2},
		},
		{
			name:     "OpenCode only",
			profile:  "remote-api-key",
			adapters: []domain.ComponentID{domain.ComponentOpenCode},
		},
		{
			name:     "Claude Code only",
			profile:  "remote-api-key",
			adapters: []domain.ComponentID{domain.ComponentClaudeCode},
		},
		{
			name:     "Codex only",
			profile:  "remote-api-key",
			adapters: []domain.ComponentID{domain.ComponentCodex},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			model := NewModel(
				&fakePreviewer{targets: defaultTargets()},
				antigravityKeyedTestCatalog(t),
				nil,
				testCredentialState(t),
			)
			configureContext7Choice(model, test.profile, test.adapters...)

			model.openMCPDetail("context7")
			if strings.Contains(
				model.View().Content,
				expectedAntigravityContext7Notice,
			) {
				t.Fatalf("unrelated detail shows keyed Antigravity notice:\n%s", model.View().Content)
			}

			preview, command := model.openPreview()
			if command != nil || preview.screen != screenPreview {
				t.Fatalf("screen = %v, command = %v", preview.screen, command)
			}
			if strings.Contains(
				preview.View().Content,
				expectedAntigravityContext7Notice,
			) {
				t.Fatalf("unrelated preview shows keyed Antigravity notice:\n%s", preview.View().Content)
			}
		})
	}
}

func TestAppliedViewDoesNotClaimSecretWasNeverResolved(t *testing.T) {
	view := (&Model{}).appliedView()
	if strings.Contains(view, "Secret values were not read or written.") {
		t.Fatal("applied view makes a false claim for keyed Antigravity")
	}
	assertContainsAll(t, view, []string{
		"Secret values were not shown in the interface or stored in MAINFRAME metadata.",
	})
}

func configureContext7Choice(
	model *Model,
	profile mcpcatalog.ProfileID,
	adapters ...domain.ComponentID,
) {
	model.selected = append([]domain.ComponentID(nil), adapters...)
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = profile
	choice.Adapters = append([]domain.ComponentID(nil), adapters...)
	if profile == "remote-api-key" {
		choice.credentialInstanceID = "context7-home"
	}
}

func assertNoticeAndSafeMetadata(t *testing.T, view string) {
	t.Helper()
	assertContainsAll(t, view, []string{
		expectedAntigravityContext7Notice,
		"Credential instance: Home (context7-home); value is resolved only during final Apply and stored in Antigravity's standard configuration.",
	})
	for _, forbidden := range []string{"CONTEXT7_HOME_KEY", "environment-secret"} {
		if strings.Contains(view, forbidden) {
			t.Fatalf("credential reference or value leaked into view:\n%s", view)
		}
	}
}

func antigravityKeyedTestCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	oldCompatibility := `"adapter": "antigravity-2",
              "status": "unsupported",
              "reason": "A plaintext-free secret reference is not verified for Antigravity 2.x."`
	newCompatibility := `"adapter": "antigravity-2",
              "status": "supported",
              "reason": ""`
	updated := strings.Replace(string(payload), oldCompatibility, newCompatibility, 1)
	if updated == string(payload) &&
		!strings.Contains(updated, newCompatibility) {
		t.Fatal("Antigravity keyed compatibility fixture is unavailable")
	}
	catalog, err := mcpcatalog.Parse([]byte(updated))
	if err != nil {
		t.Fatalf("parse test MCP catalog: %v", err)
	}
	return catalog
}
