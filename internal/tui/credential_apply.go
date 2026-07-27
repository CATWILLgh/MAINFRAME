package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

func (model *Model) updatePreview(message tea.Msg) (tea.Model, tea.Cmd) {
	key, ok := message.(tea.KeyPressMsg)
	if !ok || key.String() != "a" {
		return model, nil
	}
	plan, ok := model.reviewedPlan.(applicableReviewedPlan)
	if !ok || !plan.Applicable() {
		return model, nil
	}
	if _, ok := model.reviewer.(planApplier); !ok {
		model.err = fmt.Errorf("Plan apply is unavailable")
		return model, nil
	}
	model.applyConfirmed = false
	model.screen = screenApplyConfirm
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Apply every reviewed change now?").
			Description("The complete plan above is one transaction. Secret values are not read or written.").
			Value(&model.applyConfirmed),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) confirmPlanApply() (*Model, tea.Cmd) {
	if !model.applyConfirmed {
		model.screen = screenPreview
		return model, nil
	}
	applier, ok := model.reviewer.(planApplier)
	if !ok {
		model.err = fmt.Errorf("Plan apply is unavailable")
		model.screen = screenPreview
		return model, nil
	}
	result, err := applier.ApplyPlan(model.reviewedPlan)
	if err != nil {
		model.err = err
		model.screen = screenPreview
		return model, nil
	}
	model.credentialDirty = false
	model.appliedWarnings = append([]string(nil), result.Warnings...)
	model.screen = screenApplied
	model.err = nil
	model.form = nil
	return model, nil
}

func (model *Model) renderCredentialPreview() string {
	plan, ok := model.reviewedPlan.(credentialReviewedPlan)
	if !ok {
		return mutedStyle.Render("No credential metadata changes.")
	}
	changes := plan.CredentialChanges()
	if len(changes) == 0 {
		return mutedStyle.Render("No credential metadata changes.")
	}
	lines := []string{headingStyle.Render(
		fmt.Sprintf("Credential metadata · %d", len(changes)),
	)}
	for _, change := range changes {
		action := "Create"
		if change.Kind == credentialcatalog.ChangeUpdate {
			action = "Update"
		}
		lines = append(lines, fmt.Sprintf(
			"%s %s (%s)",
			action,
			change.After.Name,
			change.After.ID,
		))
		for _, binding := range change.After.Credentials {
			lines = append(lines, fmt.Sprintf(
				"  %s → secret reference %s",
				binding.RoleID,
				binding.Secret.Name,
			))
		}
	}
	return strings.Join(lines, "\n")
}

func (model *Model) applyConfirmView() string {
	sections := []string{
		header(),
		headingStyle.Render("Confirm complete plan"),
		bannerStyle.Render(
			"Nothing has been written yet. Confirmation applies every reviewed change as one transaction.",
		),
	}
	sections = append(sections, model.reviewedPlanSections()...)
	sections = append(sections,
		model.form.View(),
		mutedStyle.Render("enter confirm  •  b back  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}

func (model *Model) appliedView() string {
	sections := []string{
		header(),
		headingStyle.Render("Reviewed plan applied"),
		"Every confirmed change was applied successfully.",
		"Secret values were not read or written.",
	}
	if len(model.appliedWarnings) > 0 {
		sections = append(sections, bannerStyle.Render(
			"Completed with warnings:\n"+strings.Join(
				model.appliedWarnings,
				"\n",
			),
		))
	}
	sections = append(sections, mutedStyle.Render("q quit"))
	return strings.Join(sections, "\n\n")
}
