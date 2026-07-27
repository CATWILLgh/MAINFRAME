package tui

import (
	"fmt"
	"strings"

	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func mcpCredentialForm(
	server mcpcatalog.Server,
	choice *mcpChoice,
	definitions credentialcatalog.Definitions,
	instances credentialcatalog.Instances,
) *huh.Form {
	options := credentialInstanceOptions(
		server,
		choice.ProfileID,
		definitions,
		instances,
	)
	field := huh.NewSelect[credentialcatalog.InstanceID]().
		Title(server.Name + " credential instance").
		Description(
			"Select metadata from Credential services. MAINFRAME never reads the key value.",
		).
		Options(options...).
		Value(&choice.credentialInstanceID)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func credentialInstanceOptions(
	server mcpcatalog.Server,
	profileID mcpcatalog.ProfileID,
	definitions credentialcatalog.Definitions,
	instances credentialcatalog.Instances,
) []huh.Option[credentialcatalog.InstanceID] {
	service, exists := credentialServiceForProfile(
		server.ID,
		profileID,
		definitions,
	)
	if !exists {
		return nil
	}
	values := instances.ForService(service.ID)
	options := make([]huh.Option[credentialcatalog.InstanceID], len(values))
	for index, instance := range values {
		options[index] = huh.NewOption(
			instance.Name+" ("+string(instance.ID)+")",
			instance.ID,
		)
	}
	return options
}

func credentialServiceForProfile(
	serverID mcpcatalog.ServerID,
	profileID mcpcatalog.ProfileID,
	definitions credentialcatalog.Definitions,
) (credentialcatalog.ServiceDefinition, bool) {
	for _, service := range definitions.Services() {
		if service.Source.Kind == credentialcatalog.SourceMCPProfile &&
			service.Source.ServerID == string(serverID) &&
			service.Source.ProfileID == string(profileID) {
			return service, true
		}
	}
	return credentialcatalog.ServiceDefinition{}, false
}

func (model *Model) mcpCredentialView() string {
	server, exists := model.catalog.Server(model.activeMCP)
	if !exists {
		return strings.Join([]string{
			header(),
			errorStyle.Render("Selected MCP integration is unavailable."),
		}, "\n\n")
	}
	sections := []string{
		header(),
		headingStyle.Render(server.Name + " credential"),
		bannerStyle.Render(
			"Reference only — secret values stay outside MAINFRAME.",
		),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render(
		"enter save draft  •  esc back  •  ctrl+c quit",
	))
	return strings.Join(sections, "\n\n")
}

func profileRequiresCredential(
	server mcpcatalog.Server,
	profileID mcpcatalog.ProfileID,
) bool {
	profile, exists := server.Profile(profileID)
	if !exists {
		return false
	}
	return profile.Authentication.Kind == mcpcatalog.AuthenticationAPIKey ||
		profile.ServiceCredential != nil
}

func normalizeMCPChoice(server mcpcatalog.Server, choice *mcpChoice) {
	if !choice.Enabled || !profileRequiresCredential(server, choice.ProfileID) {
		choice.credentialInstanceID = ""
	}
}

func (model *Model) validateCredentialDrafts() error {
	for _, server := range model.catalog.Servers() {
		choice := model.mcpChoices[server.ID]
		if choice == nil || !choice.Enabled ||
			!profileRequiresCredential(server, choice.ProfileID) {
			continue
		}
		service, exists := credentialServiceForProfile(
			server.ID,
			choice.ProfileID,
			model.credentialDefinitions,
		)
		if !exists {
			return fmt.Errorf(
				"%s: credential service is unavailable",
				server.Name,
			)
		}
		if !instanceBelongsToService(
			choice.credentialInstanceID,
			service.ID,
			model.credentialInstances,
		) {
			return fmt.Errorf(
				"%s: create and select a credential service instance",
				server.Name,
			)
		}
	}
	return nil
}

func instanceBelongsToService(
	instanceID credentialcatalog.InstanceID,
	serviceID credentialcatalog.ServiceID,
	instances credentialcatalog.Instances,
) bool {
	for _, instance := range instances.ForService(serviceID) {
		if instance.ID == instanceID {
			return true
		}
	}
	return false
}

func (model *Model) clearCredentialDrafts() {
	for _, choice := range model.mcpChoices {
		choice.credentialInstanceID = ""
	}
}
