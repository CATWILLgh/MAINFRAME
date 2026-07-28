package tui

import (
	"fmt"
	"sort"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

type credentialMenuChoice string

const (
	credentialBack          credentialMenuChoice = ":back"
	credentialCreateSecret  credentialMenuChoice = ":create-secret"
	credentialLegacyIndexes credentialMenuChoice = ":legacy-indexes"
	credentialLegacyPreview credentialMenuChoice = ":legacy-preview"
	manualSecretReference                        = ":manual-secret-reference"
)

type credentialBindingDraft struct {
	roleID          credentialcatalog.RoleID
	name            string
	requirements    []credentialcatalog.Requirement
	referenceChoice string
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
}

type applicableReviewedPlan interface {
	Applicable() bool
}

type planApplier interface {
	ApplyPlan(ReviewedPlan) (ApplyResult, error)
}

type ApplyResult struct {
	Warnings []string
}

func (model *Model) openCredentials() (*Model, tea.Cmd) {
	model.clearLegacyReferencePreview()
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
	if model.secretCreator != nil {
		options = append(options, huh.NewOption(
			"Create a new secret", credentialCreateSecret,
		))
	}
	if model.legacyCredentialInspector != nil {
		options = append(options, huh.NewOption(
			"Inspect legacy credential locations",
			credentialLegacyIndexes,
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
	if model.credentialMenuChoice == credentialCreateSecret {
		return model.openSecretCreate()
	}
	if model.credentialMenuChoice == credentialLegacyIndexes {
		return model.openLegacyCredentialIndexes()
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
			referenceChoice: binding.Secret.Name,
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
		model.credentialInstances,
	)
	return model, model.form.Init()
}

func credentialInstanceForm(
	draft *credentialInstanceDraft,
	definitions credentialcatalog.Definitions,
	instances credentialcatalog.Instances,
) *huh.Form {
	groups := make([]*huh.Group, 0)
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
	groups = append(groups, huh.NewGroup(fields...))
	service, _ := definitions.Service(draft.serviceID)
	for index := range draft.credentials {
		role, _ := credentialRole(service, draft.credentials[index].roleID)
		credential := &draft.credentials[index]
		if credential.referenceChoice == "" {
			credential.referenceChoice = credential.name
		}
		groups = append(groups, huh.NewGroup(
			huh.NewSelect[string]().
				Title(role.Name+" secret reference").
				Description("Known references are metadata only. Choose manual entry for a new name.").
				Options(credentialReferenceOptions(instances)...).
				Value(&credential.referenceChoice),
		))
		groups = append(groups, huh.NewGroup(
			huh.NewInput().
				Title(role.Name+" new secret reference").
				Description("Name only, for example CONTEXT7_WORK_KEY. The key value is never read.").
				Value(&credential.name).
				Validate(validateSecretReferenceName),
		).WithHideFunc(func() bool {
			return credential.referenceChoice != manualSecretReference
		}))
	}
	return huh.NewForm(groups...).WithShowHelp(false)
}

func credentialReferenceOptions(
	instances credentialcatalog.Instances,
) []huh.Option[string] {
	counts := make(map[string]int)
	for _, instance := range instances.All() {
		for _, credential := range instance.Credentials {
			reference := credential.Secret
			if credentialcatalog.ValidateSecretReference(reference) == nil {
				counts[reference.Name]++
			}
		}
	}
	names := make([]string, 0, len(counts))
	for name := range counts {
		names = append(names, name)
	}
	sort.Strings(names)
	options := make([]huh.Option[string], 0, len(names)+1)
	options = append(options, huh.NewOption(
		"Enter a new reference name", manualSecretReference,
	))
	for _, name := range names {
		options = append(options, huh.NewOption(fmt.Sprintf(
			"%s — %d credential-instance references", name, counts[name],
		), name))
	}
	return options
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
			model.credentialInstances,
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
				Name:    credential.referenceName(),
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

func (draft credentialBindingDraft) referenceName() string {
	if draft.referenceChoice != manualSecretReference {
		return strings.TrimSpace(draft.referenceChoice)
	}
	return strings.TrimSpace(draft.name)
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
	if model.secretCreateNotice != "" {
		sections = append(sections, model.secretCreateNotice)
	}
	status := "Nothing has been written."
	if model.secretCreateNotice != "" {
		status = "No credential metadata or adapter configuration was changed."
	}
	sections = append(sections, mutedStyle.Render(
		status+"  •  enter open  •  b back  •  q quit",
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
