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
	plan, ok := model.reviewedPlan.(credentialReviewedPlan)
	if !ok || !plan.CredentialOnlyApplicable() {
		return model, nil
	}
	if _, ok := model.reviewer.(credentialPlanApplier); !ok {
		model.err = fmt.Errorf("Credential apply is unavailable")
		return model, nil
	}
	model.applyConfirmed = false
	model.screen = screenApplyConfirm
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Write the reviewed credential metadata now?").
			Description("Only instances.json will change. Secret values are not read or written.").
			Value(&model.applyConfirmed),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) confirmCredentialApply() (*Model, tea.Cmd) {
	if !model.applyConfirmed {
		model.screen = screenPreview
		return model, nil
	}
	applier, ok := model.reviewer.(credentialPlanApplier)
	if !ok {
		model.err = fmt.Errorf("Credential apply is unavailable")
		model.screen = screenPreview
		return model, nil
	}
	if err := applier.ApplyCredentialPlan(model.reviewedPlan); err != nil {
		model.err = err
		model.screen = screenPreview
		return model, nil
	}
	model.credentialDirty = false
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
	if plan.CredentialOnlyApplicable() {
		lines = append(lines,
			bannerStyle.Render(
				"Press a to confirm this credential-only write.",
			),
		)
	} else {
		lines = append(lines, mutedStyle.Render(
			"Apply is unavailable because this review also contains other changes.",
		))
	}
	return strings.Join(lines, "\n")
}

func (model *Model) applyConfirmView() string {
	return strings.Join([]string{
		header(),
		headingStyle.Render("Confirm credential metadata write"),
		model.renderCredentialPreview(),
		model.form.View(),
		mutedStyle.Render("enter confirm  •  b back  •  q quit"),
	}, "\n\n")
}

func (model *Model) appliedView() string {
	return strings.Join([]string{
		header(),
		headingStyle.Render("Credential metadata updated"),
		"The reviewed instances.json document was written successfully.",
		"Secret values were not read or written.",
		mutedStyle.Render("q quit"),
	}, "\n\n")
}
