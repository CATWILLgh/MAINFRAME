package tui

import (
	"errors"
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
)

func (model *Model) openLegacyCredentialTransferPlan() (*Model, tea.Cmd) {
	if model.legacyCredentialPlanner == nil {
		updated, command := model.openLegacyCredentialIndexes()
		updated.err = errors.New("Legacy transfer planning is unavailable")
		return updated, command
	}
	plan, err := model.legacyCredentialPlanner.Plan()
	if err != nil {
		updated, command := model.openLegacyCredentialIndexes()
		updated.err = errors.New(
			"Legacy transfer plan could not be built safely",
		)
		return updated, command
	}
	model.legacyCredentialTransferPlan = plan
	return model.openLegacyTransferPlanMenu()
}

func (model *Model) openLegacyTransferPlanMenu() (*Model, tea.Cmd) {
	model.ensureLegacyTransferDraft()
	model.screen = screenCredentialLegacyPlan
	model.err = nil
	model.credentialMenuChoice = credentialBack
	groups := model.legacyCredentialTransferPlan.Groups
	options := make([]huh.Option[credentialMenuChoice], 0, len(groups)+2)
	for index, group := range groups {
		label := fmt.Sprintf(
			"%s · %s — %s",
			componentName(group.ComponentID),
			strings.Join(group.SectionPath, " / "),
			proposalCountText(len(group.Proposals)),
		)
		options = append(options, huh.NewOption(
			label,
			credentialMenuChoice(fmt.Sprintf("legacy-plan-group:%d", index)),
		))
	}
	options = append(options, huh.NewOption(
		fmt.Sprintf(
			"Review transfer draft — %d/%d choices",
			len(model.legacyTransferDraftChoices),
			legacyTransferProposalCount(model.legacyCredentialTransferPlan),
		),
		credentialMenuChoice("legacy-draft-review"),
	))
	options = append(options, huh.NewOption(
		"Back to legacy locations",
		credentialBack,
	))
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Read-only legacy transfer plan").
			Options(options...).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) continueFromLegacyTransferPlan() (*Model, tea.Cmd) {
	if model.credentialMenuChoice == credentialBack {
		model.clearLegacyTransferPlan()
		return model.openLegacyCredentialIndexes()
	}
	if model.credentialMenuChoice == "legacy-draft-review" {
		return model.openLegacyTransferDraftReview()
	}
	var index int
	if _, err := fmt.Sscanf(
		string(model.credentialMenuChoice),
		"legacy-plan-group:%d",
		&index,
	); err != nil {
		model.err = errors.New("Selected transfer group is unavailable")
		return model.openLegacyTransferPlanMenu()
	}
	return model.openLegacyTransferPlanGroup(index)
}

func (model *Model) openLegacyTransferPlanGroup(
	index int,
) (*Model, tea.Cmd) {
	if index < 0 || index >= len(model.legacyCredentialTransferPlan.Groups) {
		model.err = errors.New("Selected transfer group is unavailable")
		return model.openLegacyTransferPlanMenu()
	}
	model.activeLegacyTransferPlanGroup = index
	model.screen = screenCredentialLegacyPlanGroup
	model.err = nil
	model.credentialMenuChoice = credentialBack
	group := model.legacyCredentialTransferPlan.Groups[index]
	options := make([]huh.Option[credentialMenuChoice], 0, len(group.Proposals)+1)
	for proposalIndex, proposal := range group.Proposals {
		status := "pending"
		if choice, exists := model.legacyTransferDraftChoices[legacyDraftCoordinate{
			group: index, proposal: proposalIndex,
		}]; exists {
			status = string(choice.Action)
		}
		options = append(options, huh.NewOption(
			fmt.Sprintf("%s — %s", proposal.ReferenceName, status),
			credentialMenuChoice(fmt.Sprintf(
				"legacy-proposal:%d",
				proposalIndex,
			)),
		))
	}
	options = append(options, huh.NewOption(
		"Back to transfer plan",
		credentialBack,
	))
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Transfer proposal details").
			Options(options...).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) legacyCredentialTransferPlanView() string {
	plan := model.legacyCredentialTransferPlan
	proposals := 0
	for _, group := range plan.Groups {
		proposals += len(group.Proposals)
	}
	sections := []string{
		headingStyle.Render("MAINFRAME"),
		headingStyle.Render("Read-only legacy transfer plan"),
		bannerStyle.Render(
			"Inspection only. Old files and credential metadata stay unchanged.",
		),
		fmt.Sprintf(
			"%s; source accounting: %s; content accounting: %s.",
			proposalCountText(proposals),
			plan.SourceAccounting,
			plan.ContentAccounting,
		),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(
		sections,
		mutedStyle.Render("enter inspect  •  b back  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}

func (model *Model) legacyCredentialTransferPlanGroupView() string {
	group := model.legacyCredentialTransferPlan.
		Groups[model.activeLegacyTransferPlanGroup]
	lines := make([]string, len(group.Proposals))
	for index, proposal := range group.Proposals {
		fields := make([]string, len(proposal.UnresolvedFields))
		for fieldIndex, field := range proposal.UnresolvedFields {
			fields[fieldIndex] = string(field)
		}
		lines[index] = fmt.Sprintf(
			"• %s — %s; unresolved: %s",
			proposal.ReferenceName,
			proposal.Decision,
			strings.Join(fields, ", "),
		)
	}
	sections := []string{
		headingStyle.Render("MAINFRAME"),
		headingStyle.Render(strings.Join(group.SectionPath, " / ")),
		bannerStyle.Render("Names only. Values were not read."),
		strings.Join(lines, "\n"),
		model.form.View(),
		mutedStyle.Render("enter or b back  •  q quit"),
	}
	return strings.Join(sections, "\n\n")
}

func (model *Model) clearLegacyTransferPlan() {
	model.legacyCredentialTransferPlan =
		credentialmigration.LegacyTransferPlan{}
	model.activeLegacyTransferPlanGroup = 0
	model.clearLegacyTransferDraft()
}

func proposalCountText(count int) string {
	if count == 1 {
		return "1 proposal"
	}
	return fmt.Sprintf("%d proposals", count)
}

func legacyTransferProposalCount(
	plan credentialmigration.LegacyTransferPlan,
) int {
	count := 0
	for _, group := range plan.Groups {
		count += len(group.Proposals)
	}
	return count
}
