package tui

import (
	"context"
	"fmt"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const repositoryStatsTimeout = 3 * time.Second

type mcpChoice struct {
	Initialized          bool
	Enabled              bool
	ProfileID            mcpcatalog.ProfileID
	Adapters             []domain.ComponentID
	credentialInstanceID credentialcatalog.InstanceID
}

type mcpMenuChoice string

const mcpBackToOverview mcpMenuChoice = ":back-to-overview"

type repositoryStatsMsg struct {
	ServerID   mcpcatalog.ServerID
	Generation uint64
	Stats      mcpcatalog.RepositoryStats
	Err        error
}

func (model *Model) openMCP() (*Model, tea.Cmd) {
	model.screen = screenMCP
	model.activeMCP = ""
	model.preview = lifecycle.Preview{}
	model.mcpPreview = mcpcatalog.OnboardingPreview{}
	model.err = nil
	model.ensureMCPChoices()
	model.form = mcpCatalogForm(model.catalog, model.mcpChoices, &model.mcpMenuChoice)
	model.statsGeneration++
	commands := []tea.Cmd{model.form.Init()}
	commands = append(commands, model.repositoryStatsCommands()...)
	return model, tea.Batch(commands...)
}

func (model *Model) reinitializeCurrentForm() (*Model, tea.Cmd) {
	switch model.screen {
	case screenMain:
		model.form = mainMenuForm(model)
	case screenSelection:
		model.selected = selectableSelection(model.targets, model.selected)
		model.form = selectionForm(model.targets, &model.selected)
	case screenMCP:
		model.form = mcpCatalogForm(model.catalog, model.mcpChoices, &model.mcpMenuChoice)
	case screenMCPDetail:
		server, exists := model.catalog.Server(model.activeMCP)
		if !exists {
			return model.openMCP()
		}
		model.form = mcpDetailForm(model.catalog, server, model.mcpChoices[server.ID], model.selected)
	case screenMCPCredential:
		server, exists := model.catalog.Server(model.activeMCP)
		if !exists {
			return model.openMCP()
		}
		model.form = mcpCredentialForm(
			server,
			model.mcpChoices[server.ID],
			model.credentialDefinitions,
			model.credentialInstances,
		)
	case screenDiagnostics:
		model.form = diagnosticsForm(
			&model.diagnosticsDEVEnabled,
			&model.diagnosticsFeedbackEnabled,
		)
	case screenCredentials:
		model.form = credentialCatalogForm(model)
	case screenCredentialEdit:
		model.form = credentialInstanceForm(
			&model.credentialDraft,
			model.credentialDefinitions,
			model.credentialInstances,
		)
	case screenApplyConfirm:
		model.form = huh.NewForm(huh.NewGroup(
			huh.NewConfirm().
				Title("Apply every reviewed change now?").
				Description(
					"The complete plan above is one transaction. Secret values are not read or written.",
				).
				Value(&model.applyConfirmed),
		)).WithShowHelp(false)
	default:
		model.form = mainMenuForm(model)
	}
	return model, model.form.Init()
}

func (model *Model) ensureMCPChoices() {
	for _, server := range model.catalog.Servers() {
		choice, exists := model.mcpChoices[server.ID]
		if !exists {
			choice = &mcpChoice{}
			model.mcpChoices[server.ID] = choice
		}
		if choice.Initialized {
			if !choice.Enabled {
				profile, _ := server.Profile(choice.ProfileID)
				choice.Adapters = supportedSubset(model.selected, profile)
				normalizeMCPChoice(server, choice)
				continue
			}
			choice.Adapters = selectedSubset(choice.Adapters, model.selected)
			if len(choice.Adapters) == 0 {
				choice.Enabled = false
			}
			normalizeMCPChoice(server, choice)
			continue
		}
		choice.Initialized = true
		choice.ProfileID = defaultProfile(server)
		profile, _ := server.Profile(choice.ProfileID)
		choice.Adapters = supportedSubset(model.selected, profile)
		normalizeMCPChoice(server, choice)
	}
}

func (model *Model) reconcileMCPChoices() {
	for _, server := range model.catalog.Servers() {
		choice := model.mcpChoices[server.ID]
		if choice == nil {
			continue
		}
		choice.Adapters = selectedSubset(choice.Adapters, model.selected)
		if len(choice.Adapters) == 0 {
			choice.Enabled = false
		}
		normalizeMCPChoice(server, choice)
	}
}

func (model *Model) mcpSelections() []mcpcatalog.Selection {
	selections := make([]mcpcatalog.Selection, 0)
	for _, server := range model.catalog.Servers() {
		choice := model.mcpChoices[server.ID]
		if choice == nil || !choice.Enabled {
			continue
		}
		selections = append(selections, mcpcatalog.Selection{
			ServerID: server.ID, ProfileID: choice.ProfileID,
			Adapters: append([]domain.ComponentID(nil), choice.Adapters...),
		})
	}
	return selections
}

func (model *Model) mcpCredentialBindings() []application.MCPCredentialBinding {
	bindings := make([]application.MCPCredentialBinding, 0)
	for _, server := range model.catalog.Servers() {
		choice := model.mcpChoices[server.ID]
		if choice == nil || !choice.Enabled ||
			choice.credentialInstanceID == "" {
			continue
		}
		bindings = append(bindings, application.MCPCredentialBinding{
			ServerID:   server.ID,
			ProfileID:  choice.ProfileID,
			InstanceID: choice.credentialInstanceID,
		})
	}
	return bindings
}

func (model *Model) mcpView() string {
	sections := []string{
		header(),
		headingStyle.Render("MCP integrations"),
		"Open an integration to configure it.\nChoices stay in the draft until the complete plan is reviewed.",
	}
	for _, server := range model.catalog.Servers() {
		sections = append(sections, model.mcpServerListItem(server))
	}
	sections = append(sections, model.form.View())
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render("Nothing has been applied.  •  enter open  •  b back  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func (model *Model) mcpDetailView() string {
	server, exists := model.catalog.Server(model.activeMCP)
	if !exists {
		return strings.Join([]string{header(), errorStyle.Render("Selected MCP integration is unavailable.")}, "\n\n")
	}
	sections := []string{
		header(),
		headingStyle.Render("Configure " + server.Name),
		model.mcpServerCard(server),
		bannerStyle.Render("Draft only — changes are applied with the complete plan."),
	}
	sections = append(sections, model.form.View())
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render("enter next / save draft  •  b back  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func (model *Model) mcpServerListItem(server mcpcatalog.Server) string {
	lines := []string{
		headingStyle.Render(server.Name),
		server.Summary,
		"Status: " + model.mcpChoiceStatus(server.ID),
	}
	if stats, exists := model.repositoryStats[server.ID]; exists {
		lines = append(lines, fmt.Sprintf("Popularity only: %d stars", stats.Stars))
	}
	return strings.Join(lines, "\n")
}

func (model *Model) mcpChoiceStatus(serverID mcpcatalog.ServerID) string {
	choice := model.mcpChoices[serverID]
	if choice == nil || !choice.Enabled || len(choice.Adapters) == 0 {
		return "not configured"
	}
	names := make([]string, len(choice.Adapters))
	for index, adapter := range choice.Adapters {
		names[index] = componentName(adapter)
	}
	status := "added to plan, not applied · " + strings.Join(names, ", ")
	server, exists := model.catalog.Server(serverID)
	if exists && profileRequiresCredential(server, choice.ProfileID) &&
		choice.credentialInstanceID != "" {
		status += " · credential instance selected"
	}
	return status
}

func (model *Model) mcpServerCard(server mcpcatalog.Server) string {
	lines := []string{
		headingStyle.Render(server.Name),
		server.Summary,
		fmt.Sprintf("Publisher: %s  ·  License: %s  ·  Verified %s", server.Publisher, server.License, verifiedOn(server)),
		"Repository: " + server.Repository.URL,
		"Documentation: " + server.DocumentationURL,
		"Recipe source: " + server.Profiles[0].Evidence.URL,
	}
	if stats, exists := model.repositoryStats[server.ID]; exists {
		lines = append(lines, fmt.Sprintf(
			"Popularity only: %d stars · refreshed %s",
			stats.Stars,
			stats.FetchedAt.Local().Format("2006-01-02 15:04"),
		))
	}
	return strings.Join(lines, "\n")
}

func mcpCatalogForm(
	catalog mcpcatalog.Catalog,
	choices map[mcpcatalog.ServerID]*mcpChoice,
	selected *mcpMenuChoice,
) *huh.Form {
	options := make([]huh.Option[mcpMenuChoice], 0, len(catalog.Servers())+1)
	for _, server := range catalog.Servers() {
		status := "not configured"
		choice := choices[server.ID]
		if choice != nil && choice.Enabled && len(choice.Adapters) > 0 {
			status = "draft configured"
		}
		options = append(options, huh.NewOption(
			fmt.Sprintf("%s — %s", server.Name, status), mcpMenuChoice(server.ID),
		))
	}
	options = append(options, huh.NewOption("Back to settings overview", mcpBackToOverview))
	field := huh.NewSelect[mcpMenuChoice]().
		Title("Choose an integration").
		Options(options...).
		Value(selected)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func mcpDetailForm(
	catalog mcpcatalog.Catalog,
	server mcpcatalog.Server,
	choice *mcpChoice,
	selected []domain.ComponentID,
) *huh.Form {
	confirm := huh.NewConfirm().
		Title("Include " + server.Name + " in the plan?").
		Affirmative("Add to plan").
		Negative("Not configured").
		Value(&choice.Enabled)
	details := huh.NewGroup(
		profileField(server, choice),
		adapterField(catalog, server, choice, selected),
	).WithHideFunc(func() bool { return !choice.Enabled })
	return huh.NewForm(huh.NewGroup(confirm), details).WithShowHelp(false)
}

func profileField(server mcpcatalog.Server, choice *mcpChoice) *huh.Select[mcpcatalog.ProfileID] {
	options := make([]huh.Option[mcpcatalog.ProfileID], 0, len(server.Profiles))
	for _, profile := range server.Profiles {
		options = append(options, huh.NewOption(
			fmt.Sprintf("%s — %s", profile.Name, authenticationName(profile.Authentication.Kind)),
			profile.ID,
		))
	}
	return huh.NewSelect[mcpcatalog.ProfileID]().
		Title("Connection profile").
		Options(options...).
		Value(&choice.ProfileID)
}

func adapterField(
	catalog mcpcatalog.Catalog,
	server mcpcatalog.Server,
	choice *mcpChoice,
	selected []domain.ComponentID,
) *huh.MultiSelect[domain.ComponentID] {
	return huh.NewMultiSelect[domain.ComponentID]().
		Title("Environments receiving this MCP").
		Filterable(false).
		OptionsFunc(func() []huh.Option[domain.ComponentID] {
			profile, _ := server.Profile(choice.ProfileID)
			return adapterOptions(selected, profile, choice.Adapters)
		}, &choice.ProfileID).
		Validate(func(adapters []domain.ComponentID) error {
			_, err := catalog.Preview(selected, []mcpcatalog.Selection{{
				ServerID: server.ID, ProfileID: choice.ProfileID, Adapters: adapters,
			}})
			return err
		}).
		Value(&choice.Adapters)
}

func adapterOptions(
	selected []domain.ComponentID,
	profile mcpcatalog.Profile,
	chosen []domain.ComponentID,
) []huh.Option[domain.ComponentID] {
	options := make([]huh.Option[domain.ComponentID], 0, len(selected))
	for _, adapter := range selected {
		label := componentName(adapter)
		if status, reason := profile.Support(adapter); status != mcpcatalog.Supported {
			label += " — unsupported: " + reason
		}
		options = append(options, huh.NewOption(label, adapter).Selected(contains(chosen, adapter)))
	}
	return options
}

func (model *Model) repositoryStatsCommands() []tea.Cmd {
	if model.stats == nil {
		return nil
	}
	generation := model.statsGeneration
	commands := make([]tea.Cmd, 0)
	for _, server := range model.catalog.Servers() {
		if _, cached := model.repositoryStats[server.ID]; cached {
			continue
		}
		server := server
		commands = append(commands, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), repositoryStatsTimeout)
			defer cancel()
			stats, err := model.stats.Stats(ctx, server.Repository)
			return repositoryStatsMsg{
				ServerID: server.ID, Generation: generation, Stats: stats, Err: err,
			}
		})
	}
	return commands
}

func (model *Model) applyRepositoryStats(message repositoryStatsMsg) (tea.Model, tea.Cmd) {
	if (model.screen != screenMCP && model.screen != screenMCPDetail) ||
		message.Generation != model.statsGeneration || message.Err != nil {
		return model, nil
	}
	model.repositoryStats[message.ServerID] = message.Stats
	return model, nil
}
