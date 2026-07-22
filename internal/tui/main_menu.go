package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type mainMenuChoice string

const (
	mainMenuEnvironments mainMenuChoice = "environments"
	mainMenuMCP          mainMenuChoice = "mcp"
	mainMenuDiagnostics  mainMenuChoice = "diagnostics"
	mainMenuReview       mainMenuChoice = "review"
	mainMenuExit         mainMenuChoice = "exit"
)

func (model *Model) openMain() (*Model, tea.Cmd) {
	model.screen = screenMain
	model.preview = lifecycle.Preview{}
	model.mcpPreview = mcpcatalog.OnboardingPreview{}
	model.err = nil
	model.form = mainMenuForm(model)
	return model, model.form.Init()
}

func (model *Model) continueFromMain() (*Model, tea.Cmd) {
	switch model.mainMenuChoice {
	case mainMenuEnvironments:
		return model.openSelection()
	case mainMenuMCP:
		if len(model.selected) == 0 {
			return model.blockMainCategory()
		}
		return model.openMCP()
	case mainMenuDiagnostics:
		if len(model.selected) == 0 {
			return model.blockMainCategory()
		}
		return model.openDiagnostics()
	case mainMenuReview:
		return model.openPreview()
	case mainMenuExit:
		model.clearCredentialDrafts()
		return model, tea.Quit
	default:
		return model.openSelection()
	}
}

func (model *Model) blockMainCategory() (*Model, tea.Cmd) {
	model.screen = screenMain
	model.err = fmt.Errorf("Select at least one environment first")
	model.form = mainMenuForm(model)
	return model, model.form.Init()
}

func (model *Model) openSelection() (*Model, tea.Cmd) {
	model.screen = screenSelection
	model.err = nil
	model.selected = selectableSelection(model.targets, model.selected)
	model.form = selectionForm(model.targets, &model.selected)
	return model, model.form.Init()
}

func (model *Model) mainView() string {
	sections := []string{
		header(),
		headingStyle.Render("Settings overview"),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	if len(model.selected) == 0 {
		sections = append(sections, mutedStyle.Render(
			"MCP integrations and local diagnostics require at least one environment.",
		))
	}
	sections = append(sections, mutedStyle.Render("enter open  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func mainMenuForm(model *Model) *huh.Form {
	options := []huh.Option[mainMenuChoice]{
		huh.NewOption(
			fmt.Sprintf("Environments — %d selected", len(model.selected)),
			mainMenuEnvironments,
		),
		huh.NewOption("MCP integrations — "+model.mcpMenuStatus(), mainMenuMCP),
		huh.NewOption("Local diagnostics — "+model.diagnostics.status(), mainMenuDiagnostics),
		huh.NewOption("Review complete plan", mainMenuReview),
		huh.NewOption("Exit", mainMenuExit),
	}
	field := huh.NewSelect[mainMenuChoice]().
		Title("Choose a section").
		Options(options...).
		Value(&model.mainMenuChoice)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func (model *Model) mcpMenuStatus() string {
	configured := 0
	for _, choice := range model.mcpChoices {
		if choice != nil && choice.Enabled && len(choice.Adapters) > 0 {
			configured++
		}
	}
	if configured == 0 {
		return "not configured"
	}
	return fmt.Sprintf("%d configured", configured)
}
