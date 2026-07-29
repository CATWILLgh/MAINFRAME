package tui

import (
	"strings"
	"testing"

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
