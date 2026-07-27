package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
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

func TestMainMenuReportsStartupRecoveryAndWarnings(t *testing.T) {
	state := testCredentialState(t)
	state.Recovered = true
	state.Warnings = []string{"cleanup needs attention"}
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)

	view := model.mainView()
	for _, text := range []string{
		"recovered an unfinished earlier operation",
		"Recovery warnings",
		"cleanup needs attention",
	} {
		if !strings.Contains(view, text) {
			t.Fatalf("main view does not contain %q:\n%s", text, view)
		}
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
	model.credentialDraft.credentials[0].referenceChoice = manualSecretReference
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

func TestMixedPreviewRequiresOneExplicitConfirmationBeforeApply(
	t *testing.T,
) {
	model, reviewer := mixedApplicableModel(t)

	updated, command := model.openPreview()
	if command != nil || updated.screen != screenPreview {
		t.Fatalf("screen = %v, command = %v", updated.screen, command)
	}
	if reviewer.applies != 0 {
		t.Fatal("review applied credential metadata")
	}
	assertContainsAll(t, updated.View().Content, []string{
		"Credential metadata · 1",
		"Update Home updated",
		"a review and apply",
	})

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
	assertContainsAll(t, confirm.View().Content, []string{
		"Configuration plan",
		"Credential metadata · 1",
	})
	confirm.applyConfirmed = true
	applied, command := confirm.confirmPlanApply()
	if command != nil || applied.screen != screenApplied ||
		reviewer.applies != 1 {
		t.Fatalf(
			"applied state/applications = %v/%d",
			applied.screen,
			reviewer.applies,
		)
	}
	if !strings.Contains(
		applied.View().Content,
		"transaction cleanup needs attention",
	) {
		t.Fatalf("confirmed apply warning is absent:\n%s", applied.View().Content)
	}
}

func mixedApplicableModel(t *testing.T) (*Model, *credentialTUIReviewer) {
	t.Helper()
	state := testCredentialState(t)
	updated := state.Instances.All()[0]
	updated.Name = "Home updated"
	reviewer := &credentialTUIReviewer{
		result: ApplyResult{Warnings: []string{"transaction cleanup needs attention"}},
		plan: credentialTUIPlan{
			changes: []credentialcatalog.InstanceChange{{
				Kind:   credentialcatalog.ChangeUpdate,
				Before: state.Instances.All()[0], After: updated,
			}},
			applicable: true,
			semantic:   configurationPlanFixture,
		},
	}
	model := NewModel(reviewer, testCatalog(t), nil, state)
	model.selected = []domain.ComponentID{domain.ComponentOpenCode}
	model.openMCP()
	choice := model.mcpChoices["context7"]
	choice.Enabled = true
	choice.ProfileID = "remote-api-key"
	choice.Adapters = []domain.ComponentID{domain.ComponentOpenCode}
	choice.credentialInstanceID = "context7-home"
	model.credentialDirty = true
	model.credentialInstances, _, _ = credentialcatalog.EditInstance(
		state.Instances, "context7-home", updated, state.Definitions,
	)
	return model, reviewer
}

func assertContainsAll(t *testing.T, view string, values []string) {
	t.Helper()
	for _, value := range values {
		if !strings.Contains(view, value) {
			t.Fatalf("view does not contain %q:\n%s", value, view)
		}
	}
}

func TestAppliedCredentialViewShowsExecutorWarnings(t *testing.T) {
	model := newTestModel(t, &fakePreviewer{targets: defaultTargets()})
	model.screen = screenApplied
	model.appliedWarnings = []string{"transaction cleanup needs attention"}

	view := model.View().Content
	if !strings.Contains(view, "Completed with warnings") ||
		!strings.Contains(view, "transaction cleanup needs attention") {
		t.Fatalf("apply warnings are absent:\n%s", view)
	}
}

func TestNonApplicablePreviewCannotOpenApplyConfirmation(t *testing.T) {
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

	view := model.View().Content
	if !strings.Contains(
		view,
		"Preview only. No safe apply action is available for this plan.",
	) {
		t.Fatalf("preview-only reason is absent:\n%s", view)
	}
	next, command := model.updatePreview(keyPress("a"))
	if command != nil || next.(*Model).screen != screenPreview ||
		reviewer.applies != 0 {
		t.Fatal("mixed preview opened credential apply")
	}
}

type credentialTUIReviewer struct {
	plan    credentialTUIPlan
	request application.Request
	result  ApplyResult
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

func (reviewer *credentialTUIReviewer) ApplyPlan(
	ReviewedPlan,
) (ApplyResult, error) {
	reviewer.applies++
	return reviewer.result, nil
}

type credentialTUIPlan struct {
	changes    []credentialcatalog.InstanceChange
	applicable bool
	semantic   lifecycle.Preview
}

func (plan credentialTUIPlan) Semantic() lifecycle.Preview {
	return plan.semantic
}

func (plan credentialTUIPlan) CredentialChanges() []credentialcatalog.InstanceChange {
	return append([]credentialcatalog.InstanceChange(nil), plan.changes...)
}

func (plan credentialTUIPlan) Applicable() bool {
	return plan.applicable
}
