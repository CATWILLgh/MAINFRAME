package tui

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestLegacyTransferPlanRequiresExplicitNavigationAndOnlyInspects(t *testing.T) {
	state := testCredentialState(t)
	state.LegacyInspector = &legacyIndexInspectorFixture{
		indexes: legacyCredentialIndexesFixture(),
	}
	planner := &legacyTransferPlannerFixture{
		plan: legacyTransferPlanFixture(),
	}
	state.LegacyPlanner = planner
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)

	model.credentialMenuChoice = credentialLegacyIndexes
	model, _ = model.continueFromCredentials()
	if planner.calls != 0 {
		t.Fatalf("opening legacy inventory planned %d times", planner.calls)
	}
	model.credentialMenuChoice = credentialLegacyPlan
	model, _ = model.continueFromLegacyCredentials()
	if planner.calls != 1 || model.screen != screenCredentialLegacyPlan {
		t.Fatalf("plan calls = %d; screen = %d", planner.calls, model.screen)
	}
	view := model.legacyCredentialTransferPlanView()
	for _, expected := range []string{
		"Read-only legacy transfer plan",
		"1 proposal",
		"content accounting: partial",
	} {
		if !strings.Contains(view, expected) {
			t.Fatalf("plan view omits %q:\n%s", expected, view)
		}
	}
	if strings.Contains(view, "Apply") || strings.Contains(view, "Delete") {
		t.Fatalf("plan view offers mutation:\n%s", view)
	}

	model.credentialMenuChoice = credentialMenuChoice("legacy-plan-group:0")
	model, _ = model.continueFromLegacyTransferPlan()
	if model.screen != screenCredentialLegacyPlanGroup {
		t.Fatalf("group screen = %d", model.screen)
	}
	details := model.legacyCredentialTransferPlanGroupView()
	for _, expected := range []string{
		"SAFE_KEY",
		"needs_review",
		"service_id",
		"Back to transfer plan",
	} {
		if !strings.Contains(details, expected) {
			t.Fatalf("group view omits %q:\n%s", expected, details)
		}
	}
}

func TestLegacyTransferDraftReusesExistingInstanceWithoutCatalogMutation(
	t *testing.T,
) {
	state := testCredentialState(t)
	model := newLegacyTransferDraftModel(t, state)
	before := model.credentialInstances.All()

	model, _ = model.openLegacyTransferPlanGroup(0)
	model.credentialMenuChoice = credentialMenuChoice("legacy-proposal:0")
	model, _ = model.continueFromLegacyTransferPlanGroup()
	if model.screen != screenCredentialLegacyDraftAction {
		t.Fatalf("action screen = %d", model.screen)
	}
	model.legacyDraftAction = "transfer:context7-home:api-key"
	model, _ = model.continueLegacyTransferDraftAction()

	choice, exists := model.legacyTransferDraftChoices[legacyDraftCoordinate{
		group: 0, proposal: 0,
	}]
	if !exists || choice.Action != credentialmigration.TransferChoiceTransfer ||
		choice.TargetInstanceID != "context7-home" ||
		choice.TargetRoleID != "api-key" ||
		!choice.RenameConfirmed {
		t.Fatalf("choice = %#v; exists = %t", choice, exists)
	}
	if model.credentialDirty ||
		!reflect.DeepEqual(before, model.credentialInstances.All()) {
		t.Fatal("legacy draft changed the live credential catalog")
	}

	model, _ = model.openLegacyTransferDraftReview()
	if model.screen != screenCredentialLegacyDraftReview {
		t.Fatalf("review screen = %d", model.screen)
	}
	view := model.legacyTransferDraftReviewView()
	for _, expected := range []string{
		"Transfer draft review",
		"1 transferred",
		"0 pending",
		"Manual content review is still required",
		"Nothing has been written",
	} {
		if !strings.Contains(view, expected) {
			t.Fatalf("review omits %q:\n%s", expected, view)
		}
	}
	if strings.Contains(view, "Apply") {
		t.Fatalf("review offers apply:\n%s", view)
	}
}

func TestLegacyTransferDraftCreatesSeparateInMemoryInstance(t *testing.T) {
	state := testCredentialState(t)
	model := newLegacyTransferDraftModel(t, state)
	before := model.credentialInstances.All()

	model.activeLegacyDraftProposal = legacyDraftCoordinate{
		group: 0, proposal: 0,
	}
	model.legacyDraftAction = "create:context7:api-key"
	model, _ = model.continueLegacyTransferDraftAction()
	if model.screen != screenCredentialLegacyDraftCreate {
		t.Fatalf("create screen = %d", model.screen)
	}
	model.legacyTransferInstanceDraft.id = "context7-legacy"
	model.legacyTransferInstanceDraft.name = "Legacy"
	model.legacyTransferInstanceDraft.purpose = "Transferred legacy reference"
	model, _ = model.saveLegacyTransferInstanceDraft()

	instance, exists := model.legacyTransferDraftInstances[credentialcatalog.InstanceID("context7-legacy")]
	if !exists || instance.Credentials[0].Secret.Name != "SAFE_KEY" {
		t.Fatalf("draft instance = %#v; exists = %t", instance, exists)
	}
	if model.credentialDirty ||
		!reflect.DeepEqual(before, model.credentialInstances.All()) {
		t.Fatal("legacy draft create changed the live credential catalog")
	}
}

func TestLegacyTransferDraftSkipRemainsNotRetirementReady(t *testing.T) {
	model := newLegacyTransferDraftModel(t, testCredentialState(t))
	model.activeLegacyDraftProposal = legacyDraftCoordinate{
		group: 0, proposal: 0,
	}
	model.legacyDraftAction = "skip:obsolete"
	model, _ = model.continueLegacyTransferDraftAction()
	model, _ = model.openLegacyTransferDraftReview()

	if model.legacyTransferDraftReview.RetirementReady {
		t.Fatal("skipped proposal became retirement-ready")
	}
	if !strings.Contains(
		model.legacyTransferDraftReviewView(),
		"1 skipped",
	) {
		t.Fatal("review does not report the skipped proposal")
	}
}

func TestLegacyTransferDraftRejectsInvalidNewInstanceWithoutMutation(
	t *testing.T,
) {
	model := newLegacyTransferDraftModel(t, testCredentialState(t))
	before := model.credentialInstances.All()
	model.activeLegacyDraftProposal = legacyDraftCoordinate{
		group: 0, proposal: 0,
	}
	model.legacyDraftAction = "create:context7:api-key"
	model, _ = model.continueLegacyTransferDraftAction()
	model.legacyTransferInstanceDraft.id = "INVALID ID"
	model, _ = model.saveLegacyTransferInstanceDraft()

	if model.screen != screenCredentialLegacyDraftCreate || model.err == nil {
		t.Fatalf("screen = %d; error = %v", model.screen, model.err)
	}
	if len(model.legacyTransferDraftInstances) != 0 ||
		model.credentialDirty ||
		!reflect.DeepEqual(before, model.credentialInstances.All()) {
		t.Fatal("invalid legacy draft mutated credential state")
	}
}

func TestLegacyTransferDraftDropsReplacedUnusedInstance(t *testing.T) {
	model := newLegacyTransferDraftModel(t, testCredentialState(t))
	coordinate := legacyDraftCoordinate{group: 0, proposal: 0}
	model.activeLegacyDraftProposal = coordinate
	model.legacyTransferDraftInstances = map[credentialcatalog.InstanceID]credentialcatalog.Instance{
		"context7-old-draft": {
			ID: "context7-old-draft", ServiceID: "context7",
			Name: "Old draft", Purpose: "Old draft",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key",
				Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment,
					Name:    "SAFE_KEY",
				},
			}},
		},
	}
	model.legacyTransferDraftChoices = map[legacyDraftCoordinate]credentialmigration.LegacyTransferChoice{
		coordinate: {
			Action:           credentialmigration.TransferChoiceTransfer,
			TargetInstanceID: "context7-old-draft",
			TargetRoleID:     "api-key",
		},
	}
	model.legacyDraftAction = "transfer:context7-home:api-key"
	model, _ = model.continueLegacyTransferDraftAction()

	if len(model.legacyTransferDraftInstances) != 0 {
		t.Fatalf(
			"unused instances = %#v",
			model.legacyTransferDraftInstances,
		)
	}
}

func TestLegacyTransferDraftRefreshesChangedSourcesBeforeReview(t *testing.T) {
	state := testCredentialState(t)
	planner := &legacyTransferPlannerFixture{
		plan: legacyTransferPlanFixture(),
	}
	state.LegacyPlanner = planner
	model := newLegacyTransferDraftModel(t, state)
	model.activeLegacyDraftProposal = legacyDraftCoordinate{
		group: 0, proposal: 0,
	}
	model.legacyDraftAction = "transfer:context7-home:api-key"
	model, _ = model.continueLegacyTransferDraftAction()
	planner.plan.Groups[0].Proposals[0].Occurrences = 2

	model, _ = model.openLegacyTransferDraftReview()

	if planner.calls != 1 ||
		model.screen != screenCredentialLegacyPlan ||
		model.err == nil ||
		len(model.legacyTransferDraftChoices) != 0 ||
		model.legacyCredentialTransferPlan.Groups[0].
			Proposals[0].Occurrences != 2 {
		t.Fatalf(
			"calls/screen/error/choices/plan = %d/%d/%v/%d/%#v",
			planner.calls,
			model.screen,
			model.err,
			len(model.legacyTransferDraftChoices),
			model.legacyCredentialTransferPlan,
		)
	}
}

func newLegacyTransferDraftModel(
	t *testing.T,
	state CredentialState,
) *Model {
	t.Helper()
	if state.LegacyPlanner == nil {
		state.LegacyPlanner = &legacyTransferPlannerFixture{
			plan: legacyTransferPlanFixture(),
		}
	}
	model := NewModel(
		&fakePreviewer{targets: defaultTargets()},
		testCatalog(t),
		nil,
		state,
	)
	model.legacyCredentialTransferPlan = legacyTransferPlanFixture()
	return model
}

type legacyTransferPlannerFixture struct {
	plan  credentialmigration.LegacyTransferPlan
	calls int
}

func (fixture *legacyTransferPlannerFixture) Plan() (
	credentialmigration.LegacyTransferPlan,
	error,
) {
	fixture.calls++
	return fixture.plan, nil
}

func legacyTransferPlanFixture() credentialmigration.LegacyTransferPlan {
	return credentialmigration.LegacyTransferPlan{
		ReleaseID:          "release-a",
		MigrationReadiness: credentialmigration.ReadinessManualTransferRequired,
		SourceAccounting:   credentialmigration.AccountingComplete,
		ContentAccounting:  credentialmigration.AccountingPartial,
		Groups: []credentialmigration.LegacyPlanGroup{{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SourceRole:  credentialmigration.SourceRoleSharedOriginal,
			SectionPath: []string{"Catalog", "Home"},
			Proposals: []credentialmigration.LegacyCredentialProposal{{
				ReferenceName: "SAFE_KEY",
				Occurrences:   1,
				Compatibility: credentialmigration.ReferenceCatalogCompatible,
				Decision:      credentialmigration.DecisionNeedsReview,
				UnresolvedFields: []credentialmigration.TargetField{
					credentialmigration.TargetFieldServiceID,
				},
			}},
		}},
	}
}
