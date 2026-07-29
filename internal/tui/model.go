package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type ReviewedPlan interface {
	Semantic() lifecycle.Preview
}

type PlanReviewer interface {
	Targets() []lifecycle.Target
	Review(application.Request) (ReviewedPlan, error)
}

type Model struct {
	reviewer                         PlanReviewer
	catalog                          mcpcatalog.Catalog
	stats                            mcpcatalog.StatsSource
	targets                          []lifecycle.Target
	selected                         []domain.ComponentID
	form                             *huh.Form
	screen                           screen
	preview                          lifecycle.Preview
	reviewedPlan                     ReviewedPlan
	mcpPreview                       mcpcatalog.OnboardingPreview
	mcpChoices                       map[mcpcatalog.ServerID]*mcpChoice
	mcpMenuChoice                    mcpMenuChoice
	mainMenuChoice                   mainMenuChoice
	diagnostics                      diagnostics.Desired
	diagnosticsDEVEnabled            bool
	diagnosticsFeedbackEnabled       bool
	activeMCP                        mcpcatalog.ServerID
	repositoryStats                  map[mcpcatalog.ServerID]mcpcatalog.RepositoryStats
	credentialDefinitions            credentialcatalog.Definitions
	credentialInstances              credentialcatalog.Instances
	legacyCredentialIndexes          []credentialmigration.LegacyIndex
	legacyCredentialInspector        LegacyIndexInspector
	legacyCredentialPreviewer        LegacyReferencePreviewer
	legacyCredentialPlanner          LegacyTransferPlanner
	legacyCredentialReferencePreview credentialmigration.LegacyReferenceInventory
	activeLegacyReferenceGroup       int
	legacyCredentialTransferPlan     credentialmigration.LegacyTransferPlan
	activeLegacyTransferPlanGroup    int
	legacyTransferDraftChoices       map[legacyDraftCoordinate]credentialmigration.LegacyTransferChoice
	legacyTransferDraftInstances     map[credentialcatalog.InstanceID]credentialcatalog.Instance
	activeLegacyDraftProposal        legacyDraftCoordinate
	legacyDraftAction                string
	legacyTransferInstanceDraft      credentialInstanceDraft
	legacyTransferTargetRole         credentialcatalog.RoleID
	legacyTransferDraftReview        credentialmigration.LegacyTransferDraftReview
	credentialDirty                  bool
	credentialMenuChoice             credentialMenuChoice
	activeCredential                 credentialcatalog.InstanceID
	credentialDraft                  credentialInstanceDraft
	secretCreator                    SecretCreator
	secretDraft                      secretDraft
	secretCreateConfirmed            bool
	secretCreateNotice               string
	applyConfirmed                   bool
	appliedWarnings                  []string
	startupRecovered                 bool
	startupWarnings                  []string
	statsGeneration                  uint64
	err                              error
}

func NewModel(
	reviewer PlanReviewer,
	catalog mcpcatalog.Catalog,
	stats mcpcatalog.StatsSource,
	credentialStates ...CredentialState,
) *Model {
	targets := reviewer.Targets()
	selected := make([]domain.ComponentID, 0, len(targets))
	for _, target := range targets {
		if target.Selected && targetSelectable(target) {
			selected = append(selected, target.ID)
		}
	}
	model := &Model{
		reviewer:        reviewer,
		catalog:         catalog,
		stats:           stats,
		targets:         targets,
		selected:        selected,
		mcpChoices:      make(map[mcpcatalog.ServerID]*mcpChoice),
		repositoryStats: make(map[mcpcatalog.ServerID]mcpcatalog.RepositoryStats),
		mainMenuChoice:  mainMenuEnvironments,
	}
	if len(credentialStates) > 0 {
		model.credentialDefinitions = credentialStates[0].Definitions
		model.credentialInstances = credentialStates[0].Instances.Clone()
		model.legacyCredentialInspector = credentialStates[0].LegacyInspector
		model.legacyCredentialPreviewer = credentialStates[0].LegacyPreviewer
		model.legacyCredentialPlanner = credentialStates[0].LegacyPlanner
		model.secretCreator = credentialStates[0].SecretCreator
		model.startupRecovered = credentialStates[0].Recovered
		model.startupWarnings = append(
			[]string(nil),
			credentialStates[0].Warnings...,
		)
	}
	model.form = mainMenuForm(model)
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
		return model.updatePreview(message)
	}
	if model.screen == screenApplied {
		return model, nil
	}
	updated, command := model.form.Update(message)
	model.form = updated.(*huh.Form)
	if model.form.State == huh.StateAborted {
		model.discardSecretDraft()
		model.clearCredentialDrafts()
		return model, tea.Quit
	}
	if model.form.State == huh.StateCompleted {
		switch model.screen {
		case screenMain:
			return model.continueFromMain()
		case screenSelection:
			return model.continueFromSelection()
		case screenMCP:
			return model.continueFromMCP()
		case screenMCPDetail:
			return model.continueFromMCPDetail()
		case screenMCPCredential:
			return model.backToMCPList()
		case screenDiagnostics:
			return model.continueFromDiagnostics()
		case screenCredentials:
			return model.continueFromCredentials()
		case screenCredentialLegacy:
			return model.continueFromLegacyCredentials()
		case screenCredentialLegacyPreview:
			return model.continueFromLegacyReferencePreview()
		case screenCredentialLegacyGroup:
			return model.openLegacyReferencePreviewMenu()
		case screenCredentialLegacyPlan:
			return model.continueFromLegacyTransferPlan()
		case screenCredentialLegacyPlanGroup:
			return model.continueFromLegacyTransferPlanGroup()
		case screenCredentialLegacyDraftAction:
			return model.continueLegacyTransferDraftAction()
		case screenCredentialLegacyDraftCreate:
			return model.saveLegacyTransferInstanceDraft()
		case screenCredentialLegacyDraftReview:
			return model.openLegacyTransferPlanMenu()
		case screenCredentialEdit:
			return model.saveCredentialDraft()
		case screenSecretCreate:
			return model.continueSecretCreate()
		case screenSecretCreateConfirm:
			return model.confirmSecretCreate()
		case screenApplyConfirm:
			return model.confirmPlanApply()
		}
	}
	return model, command
}

func (model *Model) openPreview() (*Model, tea.Cmd) {
	model.clearReviewedPlan()
	model.reconcileDependentDrafts()
	mcpPreview, err := model.catalog.Preview(model.selected, model.mcpSelections())
	if err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	if err := model.validateCredentialDrafts(); err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	request := application.Request{
		Components:     model.selected,
		MCPSelections:  model.mcpSelections(),
		MCPCredentials: model.mcpCredentialBindings(),
		Diagnostics:    model.diagnostics,
	}
	if model.credentialDirty {
		instances := model.credentialInstances.Clone()
		request.CredentialInstances = &instances
	}
	reviewed, err := model.reviewer.Review(request)
	if err != nil {
		model.err = err
		return model.reinitializeCurrentForm()
	}
	if reviewed == nil {
		model.err = fmt.Errorf("review returned no plan")
		return model.reinitializeCurrentForm()
	}
	model.err = nil
	model.reviewedPlan = reviewed
	model.preview = reviewed.Semantic()
	model.mcpPreview = mcpPreview
	model.screen = screenPreview
	return model, nil
}

func (model *Model) clearReviewedPlan() {
	model.reviewedPlan = nil
	model.preview = lifecycle.Preview{}
	model.mcpPreview = mcpcatalog.OnboardingPreview{}
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
			"With none selected, MCP integrations and additional DEV tools are unavailable.",
		))
	} else {
		sections = append(sections, mutedStyle.Render(
			"Return to the overview to configure MCP and additional DEV tools.",
		))
	}
	sections = append(sections, mutedStyle.Render("space toggle  •  enter save  •  b back  •  q quit"))
	return strings.Join(sections, "\n\n")
}

func (model *Model) reviewedPlanSections() []string {
	sections := []string{headingStyle.Render("Filesystem plan")}
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
	sections = append(sections, model.renderDiagnosticsPreview())
	sections = append(sections, model.renderCredentialPreview())
	return sections
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
