package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

const expectedOpenCodeContext7Notice = "OpenCode resolves the selected key only during final Apply and stores it in a private OpenCode-only file referenced from opencode.json."

func TestOpenCodeContext7KeyedNoticeAppearsInReview(t *testing.T) {
	model := NewModel(
		&credentialTUIReviewer{
			plan: credentialTUIPlan{applicable: true},
		},
		antigravityKeyedTestCatalog(t),
		nil,
		testCredentialState(t),
	)
	configureContext7Choice(
		model,
		"remote-api-key",
		domain.ComponentOpenCode,
	)

	preview, command := model.openPreview()
	if command != nil || preview.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", preview.screen, command)
	}
	if !strings.Contains(
		preview.View().Content,
		expectedOpenCodeContext7Notice,
	) {
		t.Fatalf("OpenCode private-file notice is absent")
	}
	if !strings.Contains(
		preview.View().Content,
		"value is resolved only during final Apply and stored in a private OpenCode-only file",
	) {
		t.Fatalf("OpenCode private-file credential status is absent")
	}
}
