package tui

import (
	"errors"
	"fmt"
	"reflect"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
)

type legacyDraftCoordinate struct {
	group    int
	proposal int
}

func (model *Model) ensureLegacyTransferDraft() {
	if model.legacyTransferDraftChoices == nil {
		model.legacyTransferDraftChoices =
			make(map[legacyDraftCoordinate]credentialmigration.LegacyTransferChoice)
	}
	if model.legacyTransferDraftInstances == nil {
		model.legacyTransferDraftInstances =
			make(map[credentialcatalog.InstanceID]credentialcatalog.Instance)
	}
}

func (model *Model) continueFromLegacyTransferPlanGroup() (*Model, tea.Cmd) {
	if model.credentialMenuChoice == credentialBack {
		return model.openLegacyTransferPlanMenu()
	}
	var proposal int
	if _, err := fmt.Sscanf(
		string(model.credentialMenuChoice),
		"legacy-proposal:%d",
		&proposal,
	); err != nil {
		model.err = errors.New("Selected transfer proposal is unavailable")
		return model.openLegacyTransferPlanGroup(
			model.activeLegacyTransferPlanGroup,
		)
	}
	return model.openLegacyTransferDraftAction(legacyDraftCoordinate{
		group: model.activeLegacyTransferPlanGroup, proposal: proposal,
	})
}

func (model *Model) openLegacyTransferDraftAction(
	coordinate legacyDraftCoordinate,
) (*Model, tea.Cmd) {
	if _, err := model.legacyTransferProposal(coordinate); err != nil {
		model.err = err
		return model.openLegacyTransferPlanMenu()
	}
	model.ensureLegacyTransferDraft()
	model.activeLegacyDraftProposal = coordinate
	model.screen = screenCredentialLegacyDraftAction
	model.err = nil
	model.legacyDraftAction = ":back"
	options := model.legacyTransferTargetOptions()
	options = append(options,
		huh.NewOption("Skip — duplicate", "skip:duplicate"),
		huh.NewOption("Skip — obsolete", "skip:obsolete"),
		huh.NewOption("Skip — cannot be transferred", "skip:not_transferable"),
		huh.NewOption("Back to proposal group", ":back"),
	)
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[string]().
			Title("Choose how to account for this reference").
			Options(options...).
			Value(&model.legacyDraftAction),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) legacyTransferTargetOptions() []huh.Option[string] {
	instances := append(
		model.credentialInstances.All(),
		model.legacyTransferDraftInstanceList()...,
	)
	options := make([]huh.Option[string], 0)
	for _, instance := range instances {
		for _, binding := range instance.Credentials {
			options = append(options, huh.NewOption(
				fmt.Sprintf(
					"Use %s · %s · %s",
					instance.Name,
					binding.RoleID,
					binding.Secret.Name,
				),
				fmt.Sprintf(
					"transfer:%s:%s",
					instance.ID,
					binding.RoleID,
				),
			))
		}
	}
	for _, service := range model.credentialDefinitions.Services() {
		for _, role := range service.CredentialRoles {
			options = append(options, huh.NewOption(
				fmt.Sprintf("Create %s · %s", service.Name, role.Name),
				fmt.Sprintf("create:%s:%s", service.ID, role.ID),
			))
		}
	}
	return options
}

func (model *Model) continueLegacyTransferDraftAction() (*Model, tea.Cmd) {
	model.ensureLegacyTransferDraft()
	switch {
	case model.legacyDraftAction == ":back":
		return model.openLegacyTransferPlanGroup(
			model.activeLegacyDraftProposal.group,
		)
	case strings.HasPrefix(model.legacyDraftAction, "transfer:"):
		return model.saveLegacyTransferReuse()
	case strings.HasPrefix(model.legacyDraftAction, "create:"):
		return model.openLegacyTransferInstanceDraft()
	case strings.HasPrefix(model.legacyDraftAction, "skip:"):
		return model.saveLegacyTransferSkip()
	default:
		model.err = errors.New("Selected transfer action is unavailable")
		return model.openLegacyTransferDraftAction(
			model.activeLegacyDraftProposal,
		)
	}
}

func (model *Model) saveLegacyTransferReuse() (*Model, tea.Cmd) {
	parts := strings.Split(model.legacyDraftAction, ":")
	if len(parts) != 3 {
		model.err = errors.New("Selected transfer target is unavailable")
		return model.openLegacyTransferDraftAction(
			model.activeLegacyDraftProposal,
		)
	}
	instanceID := credentialcatalog.InstanceID(parts[1])
	roleID := credentialcatalog.RoleID(parts[2])
	reference, exists := model.legacyTransferTargetReference(instanceID, roleID)
	if !exists {
		model.err = errors.New("Selected transfer target is unavailable")
		return model.openLegacyTransferDraftAction(
			model.activeLegacyDraftProposal,
		)
	}
	proposal, _ := model.legacyTransferProposal(
		model.activeLegacyDraftProposal,
	)
	model.setLegacyTransferChoice(
		model.legacyTransferChoice(
			credentialmigration.TransferChoiceTransfer,
			instanceID,
			roleID,
			reference != proposal.ReferenceName,
			"",
		),
	)
	return model.openLegacyTransferPlanGroup(
		model.activeLegacyDraftProposal.group,
	)
}

func (model *Model) saveLegacyTransferSkip() (*Model, tea.Cmd) {
	reason := credentialmigration.TransferSkipReason(
		strings.TrimPrefix(model.legacyDraftAction, "skip:"),
	)
	model.setLegacyTransferChoice(
		model.legacyTransferChoice(
			credentialmigration.TransferChoiceSkip,
			"",
			"",
			false,
			reason,
		),
	)
	return model.openLegacyTransferPlanGroup(
		model.activeLegacyDraftProposal.group,
	)
}

func (model *Model) openLegacyTransferInstanceDraft() (*Model, tea.Cmd) {
	parts := strings.Split(model.legacyDraftAction, ":")
	if len(parts) != 3 {
		model.err = errors.New("Selected credential service is unavailable")
		return model.openLegacyTransferDraftAction(
			model.activeLegacyDraftProposal,
		)
	}
	serviceID := credentialcatalog.ServiceID(parts[1])
	roleID := credentialcatalog.RoleID(parts[2])
	service, exists := model.credentialDefinitions.Service(serviceID)
	if !exists {
		model.err = errors.New("Selected credential service is unavailable")
		return model.openLegacyTransferDraftAction(
			model.activeLegacyDraftProposal,
		)
	}
	proposal, _ := model.legacyTransferProposal(
		model.activeLegacyDraftProposal,
	)
	draft := credentialInstanceDraft{
		create: true, serviceID: serviceID,
		credentials: make([]credentialBindingDraft, len(service.CredentialRoles)),
	}
	for index, role := range service.CredentialRoles {
		draft.credentials[index].roleID = role.ID
		if role.ID == roleID {
			draft.credentials[index].name = proposal.ReferenceName
			draft.credentials[index].referenceChoice = manualSecretReference
		}
	}
	model.screen = screenCredentialLegacyDraftCreate
	model.err = nil
	model.legacyTransferTargetRole = roleID
	model.legacyTransferInstanceDraft = draft
	model.form = credentialInstanceForm(
		&model.legacyTransferInstanceDraft,
		model.credentialDefinitions,
		model.legacyTransferEffectiveInstances(),
	)
	return model, model.form.Init()
}

func (model *Model) saveLegacyTransferInstanceDraft() (*Model, tea.Cmd) {
	instance := model.legacyTransferInstanceDraft.instance()
	effective := model.legacyTransferEffectiveInstances()
	_, _, err := credentialcatalog.CreateInstance(
		effective,
		instance,
		model.credentialDefinitions,
	)
	if err != nil {
		model.err = err
		model.form = credentialInstanceForm(
			&model.legacyTransferInstanceDraft,
			model.credentialDefinitions,
			effective,
		)
		return model, model.form.Init()
	}
	model.legacyTransferDraftInstances[instance.ID] = instance
	proposal, _ := model.legacyTransferProposal(
		model.activeLegacyDraftProposal,
	)
	reference, _ := bindingReference(instance, model.legacyTransferTargetRole)
	model.setLegacyTransferChoice(
		model.legacyTransferChoice(
			credentialmigration.TransferChoiceTransfer,
			instance.ID,
			model.legacyTransferTargetRole,
			reference != proposal.ReferenceName,
			"",
		),
	)
	return model.openLegacyTransferPlanGroup(
		model.activeLegacyDraftProposal.group,
	)
}

func (model *Model) openLegacyTransferDraftReview() (*Model, tea.Cmd) {
	model.ensureLegacyTransferDraft()
	freshPlan, err := model.legacyCredentialPlanner.Plan()
	if err != nil {
		updated, command := model.openLegacyTransferPlanMenu()
		updated.err = errors.New(
			"Legacy transfer plan could not be refreshed safely",
		)
		return updated, command
	}
	if !reflect.DeepEqual(freshPlan, model.legacyCredentialTransferPlan) {
		model.reconcileLegacyTransferDraft(freshPlan)
		updated, command := model.openLegacyTransferPlanMenu()
		updated.err = errors.New(
			"Legacy sources changed; matching choices were kept for the refreshed plan",
		)
		return updated, command
	}
	review, err := credentialmigration.ReviewLegacyTransferDraft(
		freshPlan,
		model.credentialInstances,
		model.credentialDefinitions,
		model.legacyTransferDraft(),
	)
	if err != nil {
		updated, command := model.openLegacyTransferPlanMenu()
		updated.err = err
		return updated, command
	}
	model.legacyTransferDraftReview = review
	model.screen = screenCredentialLegacyDraftReview
	model.err = nil
	model.credentialMenuChoice = credentialBack
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Transfer draft review").
			Options(huh.NewOption("Back to transfer plan", credentialBack)).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) legacyTransferDraft() credentialmigration.LegacyTransferDraft {
	choices := make([]credentialmigration.LegacyTransferChoice, 0)
	for groupIndex, group := range model.legacyCredentialTransferPlan.Groups {
		for proposalIndex := range group.Proposals {
			coordinate := legacyDraftCoordinate{
				group: groupIndex, proposal: proposalIndex,
			}
			if choice, exists := model.legacyTransferDraftChoices[coordinate]; exists {
				choices = append(choices, choice)
			}
		}
	}
	return credentialmigration.LegacyTransferDraft{
		ReleaseID:    model.legacyCredentialTransferPlan.ReleaseID,
		NewInstances: model.legacyTransferDraftInstanceList(),
		Choices:      choices,
	}
}

func (model *Model) legacyTransferChoice(
	action credentialmigration.TransferChoiceAction,
	instanceID credentialcatalog.InstanceID,
	roleID credentialcatalog.RoleID,
	renameConfirmed bool,
	skipReason credentialmigration.TransferSkipReason,
) credentialmigration.LegacyTransferChoice {
	proposal, _ := model.legacyTransferProposal(
		model.activeLegacyDraftProposal,
	)
	group := model.legacyCredentialTransferPlan.
		Groups[model.activeLegacyDraftProposal.group]
	return credentialmigration.LegacyTransferChoice{
		Proposal: credentialmigration.LegacyProposalIdentity{
			ComponentID:   group.ComponentID,
			ResourceID:    group.ResourceID,
			SourceRole:    group.SourceRole,
			SectionPath:   append([]string(nil), group.SectionPath...),
			ReferenceName: proposal.ReferenceName,
		},
		ExpectedOccurrences: proposal.Occurrences,
		Action:              action, TargetInstanceID: instanceID, TargetRoleID: roleID,
		RenameConfirmed: renameConfirmed, SkipReason: skipReason,
	}
}

func (model *Model) legacyTransferProposal(
	coordinate legacyDraftCoordinate,
) (credentialmigration.LegacyCredentialProposal, error) {
	if coordinate.group < 0 ||
		coordinate.group >= len(model.legacyCredentialTransferPlan.Groups) {
		return credentialmigration.LegacyCredentialProposal{},
			errors.New("Selected transfer proposal is unavailable")
	}
	proposals := model.legacyCredentialTransferPlan.
		Groups[coordinate.group].Proposals
	if coordinate.proposal < 0 || coordinate.proposal >= len(proposals) {
		return credentialmigration.LegacyCredentialProposal{},
			errors.New("Selected transfer proposal is unavailable")
	}
	return proposals[coordinate.proposal], nil
}

func (model *Model) legacyTransferTargetReference(
	instanceID credentialcatalog.InstanceID,
	roleID credentialcatalog.RoleID,
) (string, bool) {
	for _, instance := range append(
		model.credentialInstances.All(),
		model.legacyTransferDraftInstanceList()...,
	) {
		if instance.ID == instanceID {
			return bindingReference(instance, roleID)
		}
	}
	return "", false
}

func bindingReference(
	instance credentialcatalog.Instance,
	roleID credentialcatalog.RoleID,
) (string, bool) {
	for _, binding := range instance.Credentials {
		if binding.RoleID == roleID {
			return binding.Secret.Name, true
		}
	}
	return "", false
}
