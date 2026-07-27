package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestCredentialServicesAreAvailableWithoutSelectedEnvironment(t *testing.T) {
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		testCredentialState(t),
	)
	if len(model.selected) != 0 {
		t.Fatalf("selected environments = %v", model.selected)
	}
	model.mainMenuChoice = mainMenuCredentials
	updated, command := model.continueFromMain()
	if command == nil || updated.screen != screenCredentials {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
}

func TestCredentialEditRemainsDraftUntilCompleteReview(t *testing.T) {
	previewer := &fakePreviewer{targets: defaultTargets()}
	model := NewModel(
		previewer,
		testCatalog(t),
		nil,
		testCredentialState(t),
	)
	model.openCredentialEdit("context7-home")
	model.credentialDraft.name = "Home updated"
	model.credentialDraft.credentials[0].name = "CONTEXT7_HOME_KEY_V2"

	updated, command := model.saveCredentialDraft()
	if command == nil || updated.screen != screenCredentials {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if !updated.credentialDirty || previewer.calls != 0 {
		t.Fatalf(
			"dirty/review calls = %v/%d",
			updated.credentialDirty,
			previewer.calls,
		)
	}
	instance := updated.credentialInstances.All()[0]
	if instance.Name != "Home updated" ||
		instance.Credentials[0].Secret.Name != "CONTEXT7_HOME_KEY_V2" {
		t.Fatalf("draft instance = %#v", instance)
	}
	view := updated.View().Content
	if !strings.Contains(view, "Nothing has been written") {
		t.Fatalf("draft safety notice is absent:\n%s", view)
	}
}

func TestCredentialOnlyPreviewRequiresExplicitConfirmationBeforeApply(
	t *testing.T,
) {
	state := testCredentialState(t)
	updatedInstance := state.Instances.All()[0]
	updatedInstance.Name = "Home updated"
	change := credentialcatalog.InstanceChange{
		Kind:   credentialcatalog.ChangeUpdate,
		Before: state.Instances.All()[0],
		After:  updatedInstance,
	}
	reviewer := &credentialTUIReviewer{
		plan: credentialTUIPlan{
			changes:    []credentialcatalog.InstanceChange{change},
			applicable: true,
		},
	}
	model := NewModel(reviewer, testCatalog(t), nil, state)
	model.credentialDirty = true
	model.credentialInstances, _, _ = credentialcatalog.EditInstance(
		state.Instances,
		"context7-home",
		updatedInstance,
		state.Definitions,
	)

	updated, command := model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if reviewer.applies != 0 {
		t.Fatal("review applied credential metadata")
	}
	view := updated.View().Content
	for _, text := range []string{
		"Credential metadata · 1",
		"Update Home updated",
		"Press a to confirm",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("preview does not contain %q:\n%s", text, view)
		}
	}

	next, command := updated.updatePreview(keyPress("a"))
	confirm := next.(*Model)
	if command == nil || confirm.screen != screenApplyConfirm ||
		reviewer.applies != 0 {
		t.Fatalf(
			"confirmation state/applications = %v/%d",
			confirm.screen,
			reviewer.applies,
		)
	}
	confirm.applyConfirmed = true
	applied, command := confirm.confirmCredentialApply()
	if command != nil || applied.screen != screenApplied ||
		reviewer.applies != 1 {
		t.Fatalf(
			"applied state/applications = %v/%d",
			applied.screen,
			reviewer.applies,
		)
	}
}

func TestMixedPreviewCannotOpenCredentialApplyConfirmation(t *testing.T) {
	state := testCredentialState(t)
	instance := state.Instances.All()[0]
	reviewer := &credentialTUIReviewer{
		plan: credentialTUIPlan{
			changes: []credentialcatalog.InstanceChange{{
				Kind: credentialcatalog.ChangeUpdate, Before: instance,
				After: instance,
			}},
		},
	}
	model := NewModel(reviewer, testCatalog(t), nil, state)
	model.screen = screenPreview
	model.reviewedPlan = reviewer.plan

	next, command := model.updatePreview(keyPress("a"))
	if command != nil || next.(*Model).screen != screenPreview ||
		reviewer.applies != 0 {
		t.Fatal("mixed preview opened credential apply")
	}
}

type credentialTUIReviewer struct {
	plan    credentialTUIPlan
	request application.Request
	applies int
}

func (reviewer *credentialTUIReviewer) Targets() []lifecycle.Target {
	return defaultTargets()
}

func (reviewer *credentialTUIReviewer) Review(
	request application.Request,
) (ReviewedPlan, error) {
	reviewer.request = request
	return reviewer.plan, nil
}

func (reviewer *credentialTUIReviewer) ApplyCredentialPlan(
	ReviewedPlan,
) error {
	reviewer.applies++
	return nil
}

type credentialTUIPlan struct {
	changes    []credentialcatalog.InstanceChange
	applicable bool
}

func (plan credentialTUIPlan) Semantic() lifecycle.Preview {
	return lifecycle.Preview{}
}

func (plan credentialTUIPlan) CredentialChanges() []credentialcatalog.InstanceChange {
	return append([]credentialcatalog.InstanceChange(nil), plan.changes...)
}

func (plan credentialTUIPlan) CredentialOnlyApplicable() bool {
	return plan.applicable
}
