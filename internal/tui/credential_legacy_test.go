package tui

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestLegacyCredentialIndexesRemainVisibleWithoutSelectedAdapters(
	t *testing.T,
) {
	state := testCredentialState(t)
	inspector := &legacyIndexInspectorFixture{
		indexes: legacyCredentialIndexesFixture(),
	}
	state.LegacyInspector = inspector
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	if len(model.selected) != 0 {
		t.Fatalf("selected adapters = %v", model.selected)
	}

	model.openCredentials()
	view := model.credentialsView()
	if !strings.Contains(
		view,
		"Inspect legacy credential locations",
	) {
		t.Fatalf("credential view does not summarize legacy locations:\n%s", view)
	}
	if inspector.calls != 0 {
		t.Fatalf("opening credentials inspected all adapters %d times", inspector.calls)
	}
}

func TestLegacyCredentialIndexViewIsValueFreeAndReadOnly(t *testing.T) {
	state := testCredentialState(t)
	inspector := &legacyIndexInspectorFixture{
		indexes: legacyCredentialIndexesFixture(),
	}
	state.LegacyInspector = inspector
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	model.openCredentials()
	model.credentialMenuChoice = credentialLegacyIndexes

	updated, command := model.continueFromCredentials()
	if command == nil || updated.screen != screenCredentialLegacy {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if inspector.calls != 1 {
		t.Fatalf("explicit legacy inspection calls = %d", inspector.calls)
	}
	view := updated.View().Content
	for _, expected := range []string{
		"Legacy credential locations",
		"Claude Code",
		"original shared catalog location",
		"manual transfer is required",
		"Codex",
		"defensive check for a later adapter copy",
		"needs attention before transfer",
		"Old files stay unchanged",
		"OpenCode",
		"missing adapter copies are normal",
	} {
		if !strings.Contains(view, expected) {
			t.Fatalf("legacy view does not contain %q:\n%s", expected, view)
		}
	}
	for _, forbidden := range []string{
		"legacy-private-canary",
		"/Users/",
		"migration complete",
	} {
		if strings.Contains(view, forbidden) {
			t.Fatalf("legacy view exposed %q:\n%s", forbidden, view)
		}
	}
}

func TestLegacyCredentialInspectionDoesNotRenderRawErrors(t *testing.T) {
	state := testCredentialState(t)
	state.LegacyInspector = &legacyIndexInspectorFixture{
		err: errors.New("legacy-private-canary"),
	}
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	model.openCredentials()
	model.credentialMenuChoice = credentialLegacyIndexes

	updated, _ := model.continueFromCredentials()
	view := updated.View().Content
	if updated.screen != screenCredentials ||
		!strings.Contains(view, "could not be inspected safely") ||
		strings.Contains(view, "legacy-private-canary") {
		t.Fatalf("legacy inspection error view:\n%s", view)
	}
}

type legacyIndexInspectorFixture struct {
	indexes []credentialmigration.LegacyIndex
	err     error
	calls   int
}

func (fixture *legacyIndexInspectorFixture) Inspect() (
	[]credentialmigration.LegacyIndex,
	error,
) {
	fixture.calls++
	return append(
		[]credentialmigration.LegacyIndex(nil),
		fixture.indexes...,
	), fixture.err
}

func legacyCredentialIndexesFixture() []credentialmigration.LegacyIndex {
	return []credentialmigration.LegacyIndex{
		{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			State:       credentialmigration.IndexPresent,
			SourceRole:  credentialmigration.SourceRoleSharedOriginal,
			MigrationReadiness: credentialmigration.
				ReadinessManualTransferRequired,
		},
		{
			ComponentID:  domain.ComponentCodex,
			ResourceID:   "codex.credentials-index",
			State:        credentialmigration.IndexUnsafe,
			SourceRole:   credentialmigration.SourceRoleAdapterCopy,
			UnsafeReason: credentialmigration.ReasonUnsafeMode,
			MigrationReadiness: credentialmigration.
				ReadinessBlocked,
		},
		{
			ComponentID: domain.ComponentOpenCode,
			ResourceID:  "opencode.credentials-index",
			State:       credentialmigration.IndexMissing,
			SourceRole:  credentialmigration.SourceRoleAdapterCopy,
			MigrationReadiness: credentialmigration.
				ReadinessNoTransferRequired,
		},
		{
			ComponentID:            domain.ComponentAntigravity2,
			ResourceID:             "antigravity-2.credentials-index",
			State:                  credentialmigration.IndexPresent,
			SourceRole:             credentialmigration.SourceRoleAdapterCopy,
			MatchesCurrentTemplate: true,
			MigrationReadiness: credentialmigration.
				ReadinessNoTransferRequired,
		},
	}
}
