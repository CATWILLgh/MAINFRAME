package tui

import (
	"errors"
	"fmt"
	"strings"

	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func credentialField(server mcpcatalog.Server, choice *mcpChoice) *huh.Input {
	return huh.NewInput().
		Title(server.Name + " API key").
		Description("Input is masked and held only in process memory. It is not stored or applied.").
		EchoMode(huh.EchoModePassword).
		Validate(validateCredentialDraft).
		Value(&choice.credentialDraft)
}

func mcpCredentialForm(server mcpcatalog.Server, choice *mcpChoice) *huh.Form {
	return huh.NewForm(huh.NewGroup(credentialField(server, choice))).WithShowHelp(false)
}

func (model *Model) mcpCredentialView() string {
	server, exists := model.catalog.Server(model.activeMCP)
	if !exists {
		return strings.Join([]string{header(), errorStyle.Render("Selected MCP integration is unavailable.")}, "\n\n")
	}
	sections := []string{
		header(),
		headingStyle.Render(server.Name + " credential"),
		bannerStyle.Render("Private draft — held only for this running preview."),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render("enter save draft  •  esc back  •  ctrl+c quit"))
	return strings.Join(sections, "\n\n")
}

func validateCredentialDraft(value string) error {
	if !credentialDraftProvided(value) {
		return errors.New("API key is required")
	}
	return nil
}

func credentialDraftProvided(value string) bool {
	return strings.TrimSpace(value) != ""
}

func profileRequiresCredential(server mcpcatalog.Server, profileID mcpcatalog.ProfileID) bool {
	profile, exists := server.Profile(profileID)
	if !exists {
		return false
	}
	return profile.Authentication.Kind == mcpcatalog.AuthenticationAPIKey ||
		profile.ServiceCredential != nil
}

func normalizeMCPChoice(server mcpcatalog.Server, choice *mcpChoice) {
	if !choice.Enabled || !profileRequiresCredential(server, choice.ProfileID) {
		choice.credentialDraft = ""
	}
}

func (model *Model) validateCredentialDrafts() error {
	for _, server := range model.catalog.Servers() {
		choice := model.mcpChoices[server.ID]
		if choice == nil || !choice.Enabled || !profileRequiresCredential(server, choice.ProfileID) {
			continue
		}
		if err := validateCredentialDraft(choice.credentialDraft); err != nil {
			return fmt.Errorf("%s: %w", server.Name, err)
		}
	}
	return nil
}

func (model *Model) clearCredentialDrafts() {
	for _, choice := range model.mcpChoices {
		choice.credentialDraft = ""
	}
}
