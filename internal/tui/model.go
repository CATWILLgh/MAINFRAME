package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type Previewer interface {
	Targets() []lifecycle.Target
	Preview(lifecycle.PreviewRequest) (lifecycle.Preview, error)
}

type screen uint8

const (
	screenSelection screen = iota
	screenMCP
	screenMCPDetail
	screenMCPCredential
	screenPreview
)

type Model struct {
	previewer       Previewer
	catalog         mcpcatalog.Catalog
	stats           mcpcatalog.StatsSource
	targets         []lifecycle.Target
	selected        []domain.ComponentID
	form            *huh.Form
	screen          screen
	preview         lifecycle.Preview
	mcpPreview      mcpcatalog.OnboardingPreview
	mcpChoices      map[mcpcatalog.ServerID]*mcpChoice
	mcpMenuChoice   mcpMenuChoice
	activeMCP       mcpcatalog.ServerID
	repositoryStats map[mcpcatalog.ServerID]mcpcatalog.RepositoryStats
	statsGeneration uint64
	err             error
}

var (
	brandStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#7C6CFF"))
	bannerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#F4BF75"))
	headingStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#D7D5FF"))
	mutedStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#77758C"))
	errorStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FF6B8A"))
)

func NewModel(
	previewer Previewer,
	catalog mcpcatalog.Catalog,
	stats mcpcatalog.StatsSource,
) *Model {
	targets := previewer.Targets()
	selected := make([]domain.ComponentID, 0, len(targets))
	for _, target := range targets {
		if target.Selected && targetSelectable(target) {
			selected = append(selected, target.ID)
		}
	}
	model := &Model{
		previewer:       previewer,
		catalog:         catalog,
		stats:           stats,
		targets:         targets,
		selected:        selected,
		mcpChoices:      make(map[mcpcatalog.ServerID]*mcpChoice),
		repositoryStats: make(map[mcpcatalog.ServerID]mcpcatalog.RepositoryStats),
	}
	model.form = selectionForm(targets, &model.selected)
	return model
}

func (model *Model) Init() tea.Cmd {
	return model.form.Init()
}

func (model *Model) Update(message tea.Msg) (tea.Model, tea.Cmd) {
	if stats, ok := message.(repositoryStatsMsg); ok {
		return model.applyRepositoryStats(stats)
	}
	if key, ok := message.(tea.KeyPressMsg); ok {
		if updated, command, handled := model.handleGlobalKey(key); handled {
			return updated, command
		}
	}
	if model.screen == screenPreview {
		return model, nil
	}
	updated, command := model.form.Update(message)
	model.form = updated.(*huh.Form)
	if model.form.State == huh.StateAborted {
		model.clearCredentialDrafts()
		return model, tea.Quit
	}
	if model.form.State == huh.StateCompleted {
		switch model.screen {
		case screenSelection:
			return model.continueFromSelection()
		case screenMCP:
			return model.continueFromMCP()
		case screenMCPDetail:
			return model.continueFromMCPDetail()
		case screenMCPCredential:
			return model.backToMCPList()
		}
	}
	return model, command
}

func (model *Model) View() tea.View {
	content := model.selectionView()
	if model.screen == screenMCP {
		content = model.mcpView()
	} else if model.screen == screenMCPDetail {
		content = model.mcpDetailView()
	} else if model.screen == screenMCPCredential {
		content = model.mcpCredentialView()
	} else if model.screen == screenPreview {
		content = model.previewView()
	}
	view := tea.NewView(content)
	view.AltScreen = true
	view.WindowTitle = "MAINFRAME"
	return view
}

func (model *Model) openPreview() (*Model, tea.Cmd) {
	model.reconcileMCPChoices()
	mcpPreview, err := model.catalog.Preview(model.selected, model.mcpSelections())
	if err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	if err := model.validateCredentialDrafts(); err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	result, err := model.previewer.Preview(lifecycle.PreviewRequest{
		Components:    model.selected,
		MCPSelections: model.mcpSelections(),
	})
	if err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	model.err = nil
	model.preview = result
	model.mcpPreview = mcpPreview
	model.screen = screenPreview
	return model, nil
}

func (model *Model) backToSelection() (*Model, tea.Cmd) {
	model.screen = screenSelection
	model.preview = lifecycle.Preview{}
	model.mcpPreview = mcpcatalog.OnboardingPreview{}
	model.err = nil
	model.selected = selectableSelection(model.targets, model.selected)
	model.form = selectionForm(model.targets, &model.selected)
	return model, model.form.Init()
}

func (model *Model) selectionView() string {
	sections := []string{
		header(),
		headingStyle.Render("Choose environments"),
		model.form.View(),
	}
	if unavailable := unavailableTargetsView(model.targets); unavailable != "" {
		sections = append(sections, unavailable)
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	if len(model.selected) == 0 {
		sections = append(sections, mutedStyle.Render(
			"Select at least one environment to configure MCP integrations.\nWith none selected, MCP setup is skipped.",
		))
	} else {
		sections = append(sections, mutedStyle.Render("MCP integrations are configured on the next step."))
	}
	sections = append(sections, mutedStyle.Render("space toggle  •  enter next  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func (model *Model) previewView() string {
	sections := []string{header(), headingStyle.Render("Filesystem plan")}
	groups := []struct {
		title string
		kind  domain.OperationKind
	}{
		{title: "Install", kind: domain.OperationInstall},
		{title: "Adopt existing", kind: domain.OperationAdopt},
		{title: "Update", kind: domain.OperationReplace},
		{title: "Remove", kind: domain.OperationRemove},
		{title: "Stop managing", kind: domain.OperationRelinquish},
		{title: "Conflicts", kind: domain.OperationConflict},
	}
	groupCount := 0
	for _, group := range groups {
		operations := operationsByKind(model.preview.Filesystem.Operations, group.kind)
		if len(operations) == 0 {
			continue
		}
		groupCount++
		sections = append(sections, renderOperations(group.title, operations))
	}
	if groupCount == 0 {
		sections = append(sections, mutedStyle.Render("No filesystem changes."))
	}
	sections = append(sections, renderConfigurationPlan(model.preview.Configuration))
	sections = append(sections, renderMCPConfigurationPlan(model.preview.MCP))
	sections = append(sections, model.renderMCPPreview())
	sections = append(sections, mutedStyle.Render("b back  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func selectionForm(targets []lifecycle.Target, selected *[]domain.ComponentID) *huh.Form {
	options := make([]huh.Option[domain.ComponentID], 0, len(targets))
	for _, target := range targets {
		if !targetSelectable(target) {
			continue
		}
		options = append(options, huh.NewOption(
			fmt.Sprintf(
				"%s — %s%s",
				componentName(target.ID),
				statusName(target.Status),
				configurationStatus(target.Configuration),
			),
			target.ID,
		).Selected(contains(*selected, target.ID)))
	}
	field := huh.NewMultiSelect[domain.ComponentID]().
		Options(options...).
		Filterable(false).
		Value(selected)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func header() string {
	return strings.Join([]string{
		brandStyle.Render("MAINFRAME"),
		bannerStyle.Render("PLAN BEFORE APPLY"),
		mutedStyle.Render("Configure your choices first.\nNothing changes until you review and confirm the complete plan."),
		mutedStyle.Render("This build is preview-only; Apply remains disabled."),
	}, "\n")
}

func operationsByKind(
	operations []domain.Operation,
	kind domain.OperationKind,
) []domain.Operation {
	filtered := make([]domain.Operation, 0)
	for _, operation := range operations {
		if operation.Kind == kind {
			filtered = append(filtered, operation)
		}
	}
	return filtered
}

func renderOperations(title string, operations []domain.Operation) string {
	lines := []string{headingStyle.Render(fmt.Sprintf("%s · %d", title, len(operations)))}
	for _, operation := range operations {
		location := operation.Artifact.Location
		lines = append(lines, fmt.Sprintf(
			"  %s  %s · %s/%s",
			operationGlyph(operation.Kind),
			componentName(operation.ComponentID),
			location.Root,
			location.Path,
		))
	}
	return strings.Join(lines, "\n")
}

func operationGlyph(kind domain.OperationKind) string {
	switch kind {
	case domain.OperationInstall:
		return "+"
	case domain.OperationAdopt:
		return "✓"
	case domain.OperationReplace:
		return "↻"
	case domain.OperationRemove:
		return "−"
	case domain.OperationRelinquish:
		return "◇"
	default:
		return "!"
	}
}

func componentName(id domain.ComponentID) string {
	switch id {
	case domain.ComponentClaudeCode:
		return "Claude Code"
	case domain.ComponentCodex:
		return "Codex"
	case domain.ComponentOpenCode:
		return "OpenCode"
	case domain.ComponentAntigravity2:
		return "Antigravity 2.x"
	default:
		return string(id)
	}
}

func statusName(status lifecycle.TargetStatus) string {
	switch status {
	case lifecycle.StatusManaged:
		return "installed"
	case lifecycle.StatusAttention:
		return "needs attention"
	default:
		return "not detected"
	}
}

func contains(components []domain.ComponentID, id domain.ComponentID) bool {
	for _, component := range components {
		if component == id {
			return true
		}
	}
	return false
}
