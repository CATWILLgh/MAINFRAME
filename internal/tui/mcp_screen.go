package tui

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const repositoryStatsTimeout = 3 * time.Second

type mcpChoice struct {
	Initialized bool
	Enabled     bool
	ProfileID   mcpcatalog.ProfileID
	Adapters    []domain.ComponentID
}

type repositoryStatsMsg struct {
	ServerID   mcpcatalog.ServerID
	Generation uint64
	Stats      mcpcatalog.RepositoryStats
	Err        error
}

func (model *Model) openMCP() (*Model, tea.Cmd) {
	model.screen = screenMCP
	model.preview = lifecycle.Preview{}
	model.mcpPreview = mcpcatalog.OnboardingPreview{}
	model.err = nil
	model.ensureMCPChoices()
	model.form = mcpForm(model.catalog, model.mcpChoices, model.selected)
	model.statsGeneration++
	commands := []tea.Cmd{model.form.Init()}
	commands = append(commands, model.repositoryStatsCommands()...)
	return model, tea.Batch(commands...)
}

func (model *Model) reinitializeCurrentForm() (*Model, tea.Cmd) {
	if model.screen == screenMCP {
		model.form = mcpForm(model.catalog, model.mcpChoices, model.selected)
	} else {
		model.form = selectionForm(model.targets, &model.selected)
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
			choice.Adapters = selectedSubset(choice.Adapters, model.selected)
			continue
		}
		choice.Initialized = true
		choice.ProfileID = defaultProfile(server)
		profile, _ := server.Profile(choice.ProfileID)
		choice.Adapters = supportedSubset(model.selected, profile)
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

func (model *Model) mcpView() string {
	sections := []string{header(), headingStyle.Render("Optional MCP integrations")}
	for _, server := range model.catalog.Servers() {
		sections = append(sections, model.mcpServerCard(server))
	}
	sections = append(sections, model.form.View())
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render("space toggle  •  enter preview  •  b back  •  q quit"))
	return strings.Join(sections, "\n\n")
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

func mcpForm(
	catalog mcpcatalog.Catalog,
	choices map[mcpcatalog.ServerID]*mcpChoice,
	selected []domain.ComponentID,
) *huh.Form {
	groups := make([]*huh.Group, 0)
	for _, server := range catalog.Servers() {
		server := server
		choice := choices[server.ID]
		confirm := huh.NewConfirm().
			Title("Configure " + server.Name + "?").
			Affirmative("Configure").
			Negative("Skip").
			Value(&choice.Enabled)
		groups = append(groups, huh.NewGroup(confirm))
		details := huh.NewGroup(
			profileField(server, choice),
			adapterField(catalog, server, choice, selected),
		).WithHideFunc(func() bool { return !choice.Enabled })
		groups = append(groups, details)
	}
	return huh.NewForm(groups...).WithShowHelp(false)
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
	if model.screen != screenMCP || message.Generation != model.statsGeneration || message.Err != nil {
		return model, nil
	}
	model.repositoryStats[message.ServerID] = message.Stats
	return model, nil
}

func defaultProfile(server mcpcatalog.Server) mcpcatalog.ProfileID {
	for _, profile := range server.Profiles {
		if profile.Authentication.Kind == mcpcatalog.AuthenticationNone {
			return profile.ID
		}
	}
	return server.Profiles[0].ID
}

func supportedSubset(selected []domain.ComponentID, profile mcpcatalog.Profile) []domain.ComponentID {
	result := make([]domain.ComponentID, 0, len(selected))
	for _, adapter := range selected {
		if status, _ := profile.Support(adapter); status == mcpcatalog.Supported {
			result = append(result, adapter)
		}
	}
	return result
}

func selectedSubset(chosen, selected []domain.ComponentID) []domain.ComponentID {
	result := make([]domain.ComponentID, 0, len(chosen))
	for _, adapter := range chosen {
		if contains(selected, adapter) {
			result = append(result, adapter)
		}
	}
	return result
}

func verifiedOn(server mcpcatalog.Server) string {
	dates := make([]string, 0, len(server.Profiles))
	for _, profile := range server.Profiles {
		dates = append(dates, profile.Evidence.VerifiedOn)
	}
	sort.Strings(dates)
	return dates[len(dates)-1]
}

func authenticationName(kind mcpcatalog.AuthenticationKind) string {
	if kind == mcpcatalog.AuthenticationAPIKey {
		return "API key"
	}
	return "no key"
}
