package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func diagnosticsStatus(choice diagnostics.Desired) string {
	if !choice.Configured {
		return "not configured"
	}
	if !choice.Events {
		return "DEV off"
	}
	if choice.Feedback {
		return "DEV on, feedback on"
	}
	return "DEV on"
}

func (model *Model) openDiagnostics() (*Model, tea.Cmd) {
	model.screen = screenDiagnostics
	model.err = nil
	model.diagnosticsDEVEnabled = model.diagnostics.Events
	model.diagnosticsFeedbackEnabled = model.diagnostics.Feedback
	model.form = diagnosticsForm(
		&model.diagnosticsDEVEnabled,
		&model.diagnosticsFeedbackEnabled,
	)
	return model, model.form.Init()
}

func (model *Model) continueFromDiagnostics() (*Model, tea.Cmd) {
	model.diagnostics = diagnostics.Desired{
		Configured: true,
		Events:     model.diagnosticsDEVEnabled,
		Feedback:   model.diagnosticsDEVEnabled && model.diagnosticsFeedbackEnabled,
	}
	return model.openMain()
}

func (model *Model) diagnosticsView() string {
	sections := []string{
		header(),
		headingStyle.Render("Additional"),
		mutedStyle.Render(
			"Nothing is sent over the network.\n" +
				"Each environment keeps its own MAINFRAME data.\n" +
				"Harness feedback becomes available inside DEV mode.",
		),
		model.form.View(),
		mutedStyle.Render(
			"Draft only. Nothing is applied here.\n" +
				"These choices join the complete plan.\n" +
				"left/right choose  •  enter save  •  b back  •  q quit",
		),
	}
	return strings.Join(sections, "\n\n")
}

func diagnosticsForm(devEnabled, feedbackEnabled *bool) *huh.Form {
	dev := huh.NewConfirm().
		Title("Enable DEV mode?").
		Description("Keep local diagnostic event history.").
		Affirmative("Enabled").
		Negative("Disabled").
		Value(devEnabled)
	feedback := huh.NewConfirm().
		Title("Enable harness feedback?").
		Description("Let agents write local reports about MAINFRAME friction.").
		Affirmative("Enabled").
		Negative("Disabled").
		Value(feedbackEnabled)
	return huh.NewForm(
		huh.NewGroup(dev),
		huh.NewGroup(feedback).WithHideFunc(func() bool {
			return !*devEnabled
		}),
	).WithShowHelp(false)
}

func (model *Model) renderDiagnosticsPreview() string {
	lines := []string{headingStyle.Render("DEV tools draft")}
	if len(model.preview.Diagnostics.Intents) == 0 {
		return strings.Join(append(lines, mutedStyle.Render("Not configured.")), "\n")
	}
	targets := diagnosticsIntentComponents(model.preview.Diagnostics.Intents)
	first := model.preview.Diagnostics.Intents[0]
	lines = append(lines,
		diagnosticsPreviewLine("DEV event history", first.Events, targets),
		diagnosticsPreviewLine("Harness feedback", first.Feedback, targets),
	)
	if !first.Events && !first.Feedback {
		lines = append(
			lines,
			mutedStyle.Render(
				"The final reviewed plan will ensure the activation configuration is absent.",
			),
			mutedStyle.Render("Stored diagnostic history stays on this computer."),
		)
	} else {
		lines = append(lines, mutedStyle.Render(
			"The final reviewed plan will ensure each adapter is configured.",
		))
	}
	if !model.preview.Diagnostics.Executable {
		lines = append(lines, mutedStyle.Render(
			"Request-scoped review will validate these changes before Apply is enabled.",
		))
	}
	return strings.Join(lines, "\n")
}

func diagnosticsIntentComponents(intents []diagnostics.Intent) string {
	components := make([]domain.ComponentID, 0, len(intents))
	for _, intent := range intents {
		components = append(components, intent.ComponentID)
	}
	return componentNames(components)
}

func diagnosticsPreviewLine(name string, enabled bool, targets string) string {
	action := "disable"
	if enabled {
		action = "enable"
	}
	return fmt.Sprintf("  %s — %s for %s", name, action, targets)
}

func componentNames(components []domain.ComponentID) string {
	names := make([]string, 0, len(components))
	for _, component := range components {
		names = append(names, componentName(component))
	}
	return strings.Join(names, ", ")
}
