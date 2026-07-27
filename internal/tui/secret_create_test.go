package tui

import (
	"errors"
	"strings"
	"testing"
)

const secretCanary = "secret-canary-must-not-appear"

type recordingSecretCreator struct {
	calls     int
	reference string
	value     []byte
	err       error
}

func (creator *recordingSecretCreator) CreateSecret(
	reference string,
	value []byte,
) error {
	creator.calls++
	creator.reference = reference
	creator.value = append([]byte(nil), value...)
	return creator.err
}

func TestSecretCreationUsesConfirmationAndOnlyReportsReference(t *testing.T) {
	creator := &recordingSecretCreator{}
	state := testCredentialState(t)
	state.SecretCreator = creator
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()}, testCatalog(t), nil, state,
	)

	model.openSecretCreate()
	model.secretDraft.reference = "CONTEXT7_NEW_KEY"
	model.secretDraft.value = secretCanary
	updated, command := model.continueSecretCreate()
	if command == nil || updated.screen != screenSecretCreateConfirm {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	assertContainsAll(t, updated.View().Content, []string{
		"CONTEXT7_NEW_KEY", "create-only", "No credential metadata or configuration is changed",
	})
	if strings.Contains(updated.View().Content, secretCanary) {
		t.Fatalf("secret value leaked into confirmation:\n%s", updated.View().Content)
	}

	updated.secretCreateConfirmed = true
	updated, command = updated.confirmSecretCreate()
	if command == nil || updated.screen != screenCredentials {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if creator.calls != 1 || creator.reference != "CONTEXT7_NEW_KEY" ||
		string(creator.value) != secretCanary {
		t.Fatalf("creator call = %#v", creator)
	}
	view := updated.View().Content
	assertContainsAll(t, view, []string{"Stored secret reference: CONTEXT7_NEW_KEY"})
	if strings.Contains(view, secretCanary) ||
		strings.Contains(view, "Nothing has been written") {
		t.Fatalf("post-storage view is unsafe or contradictory:\n%s", view)
	}
	if updated.secretDraft.reference != "" || updated.secretDraft.value != "" {
		t.Fatalf("secret draft was retained: %#v", updated.secretDraft)
	}
}

func TestSecretCreationCancellationAndFailureDoNotLeakOrRetainValue(t *testing.T) {
	creator := &recordingSecretCreator{err: errors.New(secretCanary)}
	state := testCredentialState(t)
	state.SecretCreator = creator
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()}, testCatalog(t), nil, state,
	)

	model.openSecretCreate()
	model.secretDraft.reference = "CONTEXT7_NEW_KEY"
	model.secretDraft.value = secretCanary
	cancelled, _ := model.handleEscape()
	if creator.calls != 0 || cancelled.screen != screenCredentials {
		t.Fatalf("cancellation calls/screen = %d/%v", creator.calls, cancelled.screen)
	}
	if cancelled.secretDraft.reference != "" || cancelled.secretDraft.value != "" {
		t.Fatalf("cancelled draft was retained: %#v", cancelled.secretDraft)
	}

	cancelled.openSecretCreate()
	cancelled.secretDraft.reference = "CONTEXT7_NEW_KEY"
	cancelled.secretDraft.value = secretCanary
	cancelled.continueSecretCreate()
	cancelled.secretCreateConfirmed = true
	failed, command := cancelled.confirmSecretCreate()
	if command == nil || failed.screen != screenCredentials || creator.calls != 1 {
		t.Fatalf("failure screen/command/calls = %v/%v/%d", failed.screen, command, creator.calls)
	}
	view := failed.View().Content
	if !strings.Contains(view, "Secret could not be stored") ||
		strings.Contains(view, secretCanary) {
		t.Fatalf("unsafe storage failure view:\n%s", view)
	}
	if failed.secretDraft.reference != "" || failed.secretDraft.value != "" {
		t.Fatalf("failed draft was retained: %#v", failed.secretDraft)
	}
}

func TestSecretValueCharactersAreNotHandledAsGlobalNavigation(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.openSecretCreate()
	model.secretDraft.value = "prefix"

	for _, character := range []string{"q", "b"} {
		updated, command, handled := model.handleGlobalKey(keyPress(character))
		if handled || command != nil || updated.screen != screenSecretCreate ||
			updated.secretDraft.value != "prefix" {
			t.Fatalf(
				"key %q handled=%v screen=%v value=%q",
				character,
				handled,
				updated.screen,
				updated.secretDraft.value,
			)
		}
	}
}
