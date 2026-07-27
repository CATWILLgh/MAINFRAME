package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

type credentialMenuChoice string

const credentialBack credentialMenuChoice = ":back"

type credentialBindingDraft struct {
	roleID       credentialcatalog.RoleID
	name         string
	requirements []credentialcatalog.Requirement
}

type credentialInstanceDraft struct {
	create      bool
	serviceID   credentialcatalog.ServiceID
	id          string
	name        string
	purpose     string
	locator     string
	credentials []credentialBindingDraft
}

type credentialReviewedPlan interface {
	CredentialChanges() []credentialcatalog.InstanceChange
	CredentialOnlyApplicable() bool
}

type credentialPlanApplier interface {
	ApplyCredentialPlan(ReviewedPlan) error
}

func (model *Model) openCredentials() (*Model, tea.Cmd) {
	model.screen = screenCredentials
	model.err = nil
	model.credentialMenuChoice = credentialBack
	model.form = credentialCatalogForm(model)
	return model, model.form.Init()
}

func credentialCatalogForm(model *Model) *huh.Form {
	options := make([]huh.Option[credentialMenuChoice], 0)
	for _, service := range model.credentialDefinitions.Services() {
		options = append(options, huh.NewOption(
			"Create "+service.Name+" instance",
			credentialMenuChoice("create:"+service.ID),
		))
	}
	for _, instance := range model.credentialInstances.All() {
		options = append(options, huh.NewOption(
			"Edit "+instance.Name+" ("+string(instance.ID)+")",
			credentialMenuChoice("edit:"+instance.ID),
		))
	}
	options = append(options, huh.NewOption("Back to overview", credentialBack))
	field := huh.NewSelect[credentialMenuChoice]().
		Title("Choose a credential service instance").
		Options(options...).
		Value(&model.credentialMenuChoice)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func (model *Model) continueFromCredentials() (*Model, tea.Cmd) {
	value := string(model.credentialMenuChoice)
	if model.credentialMenuChoice == credentialBack {
		return model.openMain()
	}
	if strings.HasPrefix(value, "create:") {
		return model.openCredentialCreate(
			credentialcatalog.ServiceID(strings.TrimPrefix(value, "create:")),
		)
	}
	if strings.HasPrefix(value, "edit:") {
		return model.openCredentialEdit(
			credentialcatalog.InstanceID(strings.TrimPrefix(value, "edit:")),
		)
	}
	model.err = fmt.Errorf("Selected credential action is unavailable")
	return model.openCredentials()
}

func (model *Model) openCredentialCreate(
	serviceID credentialcatalog.ServiceID,
) (*Model, tea.Cmd) {
	service, exists := model.credentialDefinitions.Service(serviceID)
	if !exists {
		model.err = fmt.Errorf("Selected credential service is unavailable")
		return model.openCredentials()
	}
	draft := credentialInstanceDraft{
		create: true, serviceID: service.ID,
		credentials: make([]credentialBindingDraft, len(service.CredentialRoles)),
	}
	for index, role := range service.CredentialRoles {
		draft.credentials[index].roleID = role.ID
	}
	return model.openCredentialDraft(draft)
}

func (model *Model) openCredentialEdit(
	instanceID credentialcatalog.InstanceID,
) (*Model, tea.Cmd) {
	for _, instance := range model.credentialInstances.All() {
		if instance.ID == instanceID {
			return model.openCredentialDraft(draftFromInstance(instance))
		}
	}
	model.err = fmt.Errorf("Selected credential instance is unavailable")
	return model.openCredentials()
}

func draftFromInstance(
	instance credentialcatalog.Instance,
) credentialInstanceDraft {
	draft := credentialInstanceDraft{
		serviceID: instance.ServiceID, id: string(instance.ID),
		name: instance.Name, purpose: instance.Purpose, locator: instance.Locator,
		credentials: make([]credentialBindingDraft, len(instance.Credentials)),
	}
	for index, binding := range instance.Credentials {
		draft.credentials[index] = credentialBindingDraft{
			roleID: binding.RoleID, name: binding.Secret.Name,
			requirements: append(
				[]credentialcatalog.Requirement(nil),
				binding.Requirements...,
			),
		}
	}
	return draft
}

func (model *Model) openCredentialDraft(
	draft credentialInstanceDraft,
) (*Model, tea.Cmd) {
	model.screen = screenCredentialEdit
	model.err = nil
	model.activeCredential = credentialcatalog.InstanceID(draft.id)
	model.credentialDraft = draft
	model.form = credentialInstanceForm(
		&model.credentialDraft,
		model.credentialDefinitions,
	)
	return model, model.form.Init()
}

func credentialInstanceForm(
	draft *credentialInstanceDraft,
	definitions credentialcatalog.Definitions,
) *huh.Form {
	fields := make([]huh.Field, 0)
	if draft.create {
		fields = append(fields, huh.NewInput().
			Title("Instance ID").
			Description("Stable lowercase name, for example context7-work.").
			Value(&draft.id))
	}
	fields = append(fields,
		huh.NewInput().Title("Display name").Value(&draft.name),
		huh.NewInput().Title("Purpose").Value(&draft.purpose),
		huh.NewInput().Title("Locator (optional)").Value(&draft.locator),
	)
	service, _ := definitions.Service(draft.serviceID)
	for index := range draft.credentials {
		role, _ := credentialRole(service, draft.credentials[index].roleID)
		fields = append(fields, huh.NewInput().
			Title(role.Name+" secret reference").
			Description("Name only, for example CONTEXT7_WORK_KEY. The key value is never read.").
			Value(&draft.credentials[index].name))
	}
	return huh.NewForm(huh.NewGroup(fields...)).WithShowHelp(false)
}

func credentialRole(
	service credentialcatalog.ServiceDefinition,
	id credentialcatalog.RoleID,
) (credentialcatalog.CredentialRole, bool) {
	for _, role := range service.CredentialRoles {
		if role.ID == id {
			return role, true
		}
	}
	return credentialcatalog.CredentialRole{}, false
}

func (model *Model) saveCredentialDraft() (*Model, tea.Cmd) {
	instance := model.credentialDraft.instance()
	var (
		updated credentialcatalog.Instances
		err     error
	)
	if model.credentialDraft.create {
		updated, _, err = credentialcatalog.CreateInstance(
			model.credentialInstances,
			instance,
			model.credentialDefinitions,
		)
	} else {
		updated, _, err = credentialcatalog.EditInstance(
			model.credentialInstances,
			model.activeCredential,
			instance,
			model.credentialDefinitions,
		)
	}
	if err != nil {
		model.err = err
		model.form = credentialInstanceForm(
			&model.credentialDraft,
			model.credentialDefinitions,
		)
		return model, model.form.Init()
	}
	model.credentialInstances = updated
	model.credentialDirty = true
	return model.openCredentials()
}

func (draft credentialInstanceDraft) instance() credentialcatalog.Instance {
	bindings := make([]credentialcatalog.CredentialBinding, len(draft.credentials))
	for index, credential := range draft.credentials {
		bindings[index] = credentialcatalog.CredentialBinding{
			RoleID: credential.roleID,
			Secret: credentialcatalog.SecretReference{
				Backend: credentialcatalog.BackendSecretEnvironment,
				Name:    strings.TrimSpace(credential.name),
			},
			Requirements: append(
				[]credentialcatalog.Requirement(nil),
				credential.requirements...,
			),
		}
	}
	return credentialcatalog.Instance{
		ID:        credentialcatalog.InstanceID(strings.TrimSpace(draft.id)),
		ServiceID: draft.serviceID, Name: strings.TrimSpace(draft.name),
		Purpose: strings.TrimSpace(draft.purpose),
		Locator: strings.TrimSpace(draft.locator), Credentials: bindings,
	}
}

func (model *Model) credentialsView() string {
	sections := []string{
		header(),
		headingStyle.Render("Credential services"),
		"Store descriptions and secret reference names here. Secret values remain outside MAINFRAME.",
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render(
		"Nothing has been written.  •  enter open  •  b back  •  q quit",
	))
	return strings.Join(sections, "\n\n")
}

func (model *Model) credentialEditView() string {
	service, _ := model.credentialDefinitions.Service(
		model.credentialDraft.serviceID,
	)
	sections := []string{
		header(),
		headingStyle.Render("Configure " + service.Name),
		bannerStyle.Render(
			"Draft only — review the complete plan before any metadata is written.",
		),
		"The form accepts secret reference names only. It never asks for or reads key values.",
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render(
		"enter save draft  •  b back  •  q quit",
	))
	return strings.Join(sections, "\n\n")
}
