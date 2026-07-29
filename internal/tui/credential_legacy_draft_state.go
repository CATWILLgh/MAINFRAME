package tui

import (
	"reflect"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
)

func (model *Model) reconcileLegacyTransferDraft(
	fresh credentialmigration.LegacyTransferPlan,
) {
	choices := make(
		map[legacyDraftCoordinate]credentialmigration.LegacyTransferChoice,
	)
	for groupIndex, group := range fresh.Groups {
		for proposalIndex, proposal := range group.Proposals {
			for _, choice := range model.legacyTransferDraftChoices {
				if legacyTransferChoiceMatches(group, proposal, choice) {
					choices[legacyDraftCoordinate{
						group: groupIndex, proposal: proposalIndex,
					}] = choice
					break
				}
			}
		}
	}
	model.legacyCredentialTransferPlan = fresh
	model.legacyTransferDraftChoices = choices
	model.pruneLegacyTransferDraftInstances()
}

func legacyTransferChoiceMatches(
	group credentialmigration.LegacyPlanGroup,
	proposal credentialmigration.LegacyCredentialProposal,
	choice credentialmigration.LegacyTransferChoice,
) bool {
	return choice.Proposal.ComponentID == group.ComponentID &&
		choice.Proposal.ResourceID == group.ResourceID &&
		choice.Proposal.SourceRole == group.SourceRole &&
		reflect.DeepEqual(choice.Proposal.SectionPath, group.SectionPath) &&
		choice.Proposal.ReferenceName == proposal.ReferenceName &&
		choice.ExpectedOccurrences == proposal.Occurrences
}

func (model *Model) setLegacyTransferChoice(
	choice credentialmigration.LegacyTransferChoice,
) {
	model.legacyTransferDraftChoices[model.activeLegacyDraftProposal] = choice
	model.pruneLegacyTransferDraftInstances()
}

func (model *Model) pruneLegacyTransferDraftInstances() {
	for instanceID := range model.legacyTransferDraftInstances {
		used := false
		for _, draftChoice := range model.legacyTransferDraftChoices {
			if draftChoice.Action == credentialmigration.TransferChoiceTransfer &&
				draftChoice.TargetInstanceID == instanceID {
				used = true
				break
			}
		}
		if !used {
			delete(model.legacyTransferDraftInstances, instanceID)
		}
	}
}

func (model *Model) legacyTransferDraftInstanceList() []credentialcatalog.Instance {
	ids := make([]string, 0, len(model.legacyTransferDraftInstances))
	for id := range model.legacyTransferDraftInstances {
		ids = append(ids, string(id))
	}
	sort.Strings(ids)
	instances := make([]credentialcatalog.Instance, 0, len(ids))
	for _, id := range ids {
		instances = append(
			instances,
			model.legacyTransferDraftInstances[credentialcatalog.InstanceID(id)],
		)
	}
	return instances
}

func (model *Model) legacyTransferEffectiveInstances() credentialcatalog.Instances {
	instances, err := credentialcatalog.BuildInstances(
		append(
			model.credentialInstances.All(),
			model.legacyTransferDraftInstanceList()...,
		),
		model.credentialDefinitions,
	)
	if err != nil {
		return model.credentialInstances
	}
	return instances
}

func (model *Model) clearLegacyTransferDraft() {
	model.legacyTransferDraftChoices = nil
	model.legacyTransferDraftInstances = nil
	model.activeLegacyDraftProposal = legacyDraftCoordinate{}
	model.legacyDraftAction = ""
	model.legacyTransferInstanceDraft = credentialInstanceDraft{}
	model.legacyTransferTargetRole = ""
	model.legacyTransferDraftReview =
		credentialmigration.LegacyTransferDraftReview{}
}
