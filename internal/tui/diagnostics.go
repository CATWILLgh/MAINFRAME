package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type diagnosticsFeature string

const (
	diagnosticsEvents   diagnosticsFeature = "events"
	diagnosticsFeedback diagnosticsFeature = "feedback"
)

func diagnosticsStatus(choice diagnostics.Desired) string {
	if !choice.Configured {
		return "not configured"
	}
	enabled := 0
	if choice.Events {
		enabled++
	}
	if choice.Feedback {
		enabled++
	}
	return fmt.Sprintf("%d of 2 enabled", enabled)
}

func (model *Model) openDiagnostics() (*Model, tea.Cmd) {
	model.screen = screenDiagnostics
	model.err = nil
	model.diagnosticsSelected = selectedDiagnostics(model.diagnostics)
	model.form = diagnosticsForm(&model.diagnosticsSelected)
	return model, model.form.Init()
}

func (model *Model) continueFromDiagnostics() (*Model, tea.Cmd) {
	model.diagnostics = diagnostics.Desired{
		Configured: true,
		Events:     containsDiagnostic(model.diagnosticsSelected, diagnosticsEvents),
		Feedback:   containsDiagnostic(model.diagnosticsSelected, diagnosticsFeedback),
	}
	return model.openMain()
}

func (model *Model) diagnosticsView() string {
	sections := []string{
		header(),
		headingStyle.Render("Local diagnostics"),
		mutedStyle.Render(
			"Nothing is sent over the network.\n" +
				"Each environment keeps its own MAINFRAME data.\n" +
				"Events reuse the local SQLite history from DEV mode.\n" +
				"Harness feedback creates local friction reports.",
		),
		model.form.View(),
		mutedStyle.Render(
			"Draft only. Nothing is applied here.\n" +
				"These choices join the complete plan.\n" +
				"space toggle  •  enter save  •  b back  •  q quit",
		),
	}
	return strings.Join(sections, "\n\n")
}

func diagnosticsForm(selected *[]diagnosticsFeature) *huh.Form {
	field := huh.NewMultiSelect[diagnosticsFeature]().
		Title("Choose what to keep locally").
		Filterable(false).
		Height(3).
		Options(
			huh.NewOption("Diagnostic event history", diagnosticsEvents).
				Selected(containsDiagnostic(*selected, diagnosticsEvents)),
			huh.NewOption("Harness feedback reports", diagnosticsFeedback).
				Selected(containsDiagnostic(*selected, diagnosticsFeedback)),
		).
		Value(selected)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func selectedDiagnostics(choice diagnostics.Desired) []diagnosticsFeature {
	selected := make([]diagnosticsFeature, 0, 2)
	if choice.Events {
		selected = append(selected, diagnosticsEvents)
	}
	if choice.Feedback {
		selected = append(selected, diagnosticsFeedback)
	}
	return selected
}

func containsDiagnostic(selected []diagnosticsFeature, feature diagnosticsFeature) bool {
	for _, candidate := range selected {
		if candidate == feature {
			return true
		}
	}
	return false
}

func (model *Model) renderDiagnosticsPreview() string {
	lines := []string{headingStyle.Render("Local diagnostics draft")}
	if len(model.preview.Diagnostics.Intents) == 0 {
		return strings.Join(append(lines, mutedStyle.Render("Not configured.")), "\n")
	}
	targets := diagnosticsIntentComponents(model.preview.Diagnostics.Intents)
	first := model.preview.Diagnostics.Intents[0]
	lines = append(lines,
		diagnosticsPreviewLine("Local event history", first.Events, targets),
		diagnosticsPreviewLine("Harness feedback", first.Feedback, targets),
		mutedStyle.Render("Preview only: local diagnostics are not yet part of the executable plan."),
	)
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
