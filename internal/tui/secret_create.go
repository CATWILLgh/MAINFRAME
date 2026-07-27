package tui

import (
	"errors"
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

type secretDraft struct {
	reference string
	value     string
}

func (model *Model) openSecretCreate() (*Model, tea.Cmd) {
	model.screen = screenSecretCreate
	model.err = nil
	model.secretCreateNotice = ""
	model.secretDraft = secretDraft{}
	model.form = secretCreateForm(&model.secretDraft)
	return model, model.form.Init()
}

func secretCreateForm(draft *secretDraft) *huh.Form {
	return huh.NewForm(huh.NewGroup(
		huh.NewInput().
			Title("Secret reference name").
			Description("Uppercase name only, for example CONTEXT7_WORK_KEY.").
			Value(&draft.reference).
			Validate(validateSecretReferenceName),
		huh.NewInput().
			Title("Secret value").
			Description("Entered value is masked and is not shown again.").
			EchoMode(huh.EchoModePassword).
			Value(&draft.value).
			Validate(validateSecretValue),
	)).WithShowHelp(false)
}

func validateSecretReferenceName(name string) error {
	return credentialcatalog.ValidateSecretReference(
		credentialcatalog.SecretReference{
			Backend: credentialcatalog.BackendSecretEnvironment,
			Name:    strings.TrimSpace(name),
		},
	)
}

func validateSecretValue(value string) error {
	if value == "" {
		return errors.New("secret value is required")
	}
	return nil
}

func (model *Model) continueSecretCreate() (*Model, tea.Cmd) {
	if model.secretCreator == nil {
		model.discardSecretDraft()
		return model.openCredentialsWithSecretError("Secret storage is unavailable")
	}
	model.screen = screenSecretCreateConfirm
	model.secretCreateConfirmed = false
	model.form = secretCreateConfirmForm(&model.secretCreateConfirmed)
	return model, model.form.Init()
}

func secretCreateConfirmForm(confirmed *bool) *huh.Form {
	return huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Store this new secret now?").
			Description("This creates a secret only; it does not change credential metadata or configuration.").
			Value(confirmed),
	)).WithShowHelp(false)
}

func (model *Model) confirmSecretCreate() (*Model, tea.Cmd) {
	reference := strings.TrimSpace(model.secretDraft.reference)
	if !model.secretCreateConfirmed {
		model.discardSecretDraft()
		return model.openCredentials()
	}
	value := []byte(model.secretDraft.value)
	defer clearSecretBytes(value)
	defer model.discardSecretDraft()
	if err := model.secretCreator.CreateSecret(reference, value); err != nil {
		return model.openCredentialsWithSecretError("Secret could not be stored")
	}
	model.secretCreateNotice = "Stored secret reference: " + reference
	return model.openCredentials()
}

func (model *Model) openCredentialsWithSecretError(
	message string,
) (*Model, tea.Cmd) {
	updated, command := model.openCredentials()
	updated.err = errors.New(message)
	return updated, command
}

func (model *Model) discardSecretDraft() {
	model.secretDraft.reference = ""
	model.secretDraft.value = ""
	model.secretCreateConfirmed = false
}

func clearSecretBytes(value []byte) {
	for index := range value {
		value[index] = 0
	}
}

func (model *Model) secretCreateView() string {
	sections := []string{
		header(),
		headingStyle.Render("Create a new secret"),
		bannerStyle.Render("The value is masked and is never shown in this interface."),
		model.form.View(),
		mutedStyle.Render("enter continue  •  esc cancel  •  q quit"),
	}
	return strings.Join(sections, "\n\n")
}

func (model *Model) secretCreateConfirmView() string {
	sections := []string{
		header(),
		headingStyle.Render("Confirm new secret"),
		fmt.Sprintf("Secret reference: %s", strings.TrimSpace(model.secretDraft.reference)),
		"create-only behavior. No credential metadata or configuration is changed by this action.",
		model.form.View(),
		mutedStyle.Render("enter confirm  •  esc cancel  •  q quit"),
	}
	return strings.Join(sections, "\n\n")
}
