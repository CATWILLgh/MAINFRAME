package credentialmigration

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

func TestReviewLegacyTransferDraftRejectsInvalidChoiceState(t *testing.T) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(
		t,
		definitions,
		legacyDraftInstance("dokploy-home", "Home", "SHARED_KEY"),
	)
	plan := legacyDraftPlan()
	plan.Groups = plan.Groups[:1]
	base := LegacyTransferChoice{
		Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
		ExpectedOccurrences: 2,
		Action:              TransferChoiceTransfer,
		TargetInstanceID:    "dokploy-home",
		TargetRoleID:        "api-key",
	}
	for name, mutate := range map[string]func(*LegacyTransferChoice){
		"transfer with skip reason": func(choice *LegacyTransferChoice) {
			choice.SkipReason = TransferSkipObsolete
		},
		"missing target role": func(choice *LegacyTransferChoice) {
			choice.TargetRoleID = "missing"
		},
		"skip with target": func(choice *LegacyTransferChoice) {
			choice.Action = TransferChoiceSkip
			choice.SkipReason = TransferSkipDuplicate
		},
		"invalid skip reason": func(choice *LegacyTransferChoice) {
			choice.Action = TransferChoiceSkip
			choice.TargetInstanceID = ""
			choice.TargetRoleID = ""
			choice.SkipReason = "other"
		},
	} {
		t.Run(name, func(t *testing.T) {
			choice := base
			mutate(&choice)
			_, err := ReviewLegacyTransferDraft(
				plan,
				current,
				definitions,
				LegacyTransferDraft{
					ReleaseID: plan.ReleaseID,
					Choices:   []LegacyTransferChoice{choice},
				},
			)
			if err == nil {
				t.Fatal("ReviewLegacyTransferDraft() error = nil")
			}
		})
	}
}

func TestReviewLegacyTransferDraftRejectsUnusedNewInstance(t *testing.T) {
	definitions := legacyDraftDefinitions(t)
	plan := legacyDraftPlan()
	_, err := ReviewLegacyTransferDraft(
		plan,
		legacyDraftInstances(t, definitions),
		definitions,
		LegacyTransferDraft{
			ReleaseID: plan.ReleaseID,
			NewInstances: []credentialcatalog.Instance{
				legacyDraftInstance("dokploy-unused", "Unused", "UNUSED_KEY"),
			},
			Choices: []LegacyTransferChoice{},
		},
	)
	if err == nil {
		t.Fatal("ReviewLegacyTransferDraft() error = nil")
	}
}

func TestReviewLegacyTransferDraftReportsCompleteAccountingOnly(t *testing.T) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(
		t,
		definitions,
		legacyDraftInstance("dokploy-home", "Home", "SHARED_KEY"),
	)
	plan := legacyDraftPlan()
	plan.Groups = plan.Groups[:1]
	plan.ContentAccounting = AccountingComplete
	review, err := ReviewLegacyTransferDraft(
		plan,
		current,
		definitions,
		LegacyTransferDraft{
			ReleaseID: plan.ReleaseID,
			Choices: []LegacyTransferChoice{{
				Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
				ExpectedOccurrences: 2,
				Action:              TransferChoiceTransfer,
				TargetInstanceID:    "dokploy-home",
				TargetRoleID:        "api-key",
			}},
		},
	)
	if err != nil {
		t.Fatalf("ReviewLegacyTransferDraft() error = %v", err)
	}
	if !review.RetirementReady || review.ManualContentReviewRequired {
		t.Fatalf("review = %#v", review)
	}
}
