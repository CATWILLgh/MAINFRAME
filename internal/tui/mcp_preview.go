package tui

import (
	"fmt"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func (model *Model) renderMCPPreview() string {
	lines := []string{headingStyle.Render("MCP onboarding choices")}
	if len(model.mcpPreview.Connections) == 0 {
		lines = append(lines, mutedStyle.Render("No MCP integrations selected."))
	} else {
		for _, connection := range model.mcpPreview.Connections {
			lines = append(lines, model.renderMCPConnection(connection))
		}
	}
	lines = append(lines, mutedStyle.Render(
		"Draft choice. Configuration changes only after complete-plan confirmation.",
	))
	return strings.Join(lines, "\n")
}

func renderMCPConfigurationPlan(plan mcpconfiguration.Plan) string {
	lines := []string{headingStyle.Render("MCP configuration plan")}
	migrationNotices := renderMCPMigrationNotices(plan.Migrations)
	lines = append(lines, migrationNotices...)
	if len(plan.Intents) == 0 && len(migrationNotices) == 0 {
		return strings.Join(append(lines, mutedStyle.Render("No MCP configuration changes.")), "\n")
	}
	for _, intent := range plan.Intents {
		line := fmt.Sprintf(
			"  %s · %s · %s",
			componentName(intent.ComponentID),
			intent.ServerID,
			intent.Kind,
		)
		if intent.Reason != "" {
			line += "\n    " + intent.Reason
		}
		lines = append(lines, line)
	}
	if plan.Blocking {
		lines = append(lines, errorStyle.Render("MCP configuration has blocking conflicts."))
	}
	return strings.Join(lines, "\n")
}

func renderMCPMigrationNotices(
	migrations []mcpconfiguration.MigrationAssessment,
) []string {
	notices := make([]string, 0, len(migrations))
	for _, migration := range migrations {
		if migration.ComponentID != domain.ComponentAntigravity2 {
			continue
		}
		var notice string
		style := bannerStyle
		switch migration.State {
		case mcpconfiguration.MigrationLegacyOnly:
			notice = "Legacy Antigravity MCP configuration detected. " +
				"A migration is required before Antigravity MCP changes."
		case mcpconfiguration.MigrationEquivalentDual:
			notice = "Both Antigravity MCP locations contain equivalent configuration. " +
				"Cleanup or migration is required before Antigravity MCP changes."
		case mcpconfiguration.MigrationConflictingDual:
			notice = "Antigravity MCP locations differ. " +
				"Resolve them explicitly before Antigravity MCP changes."
			style = errorStyle
		case mcpconfiguration.MigrationInvalidLegacy:
			notice = "Legacy Antigravity MCP configuration cannot be safely inspected. " +
				"Resolve it explicitly before Antigravity MCP changes."
			style = errorStyle
		}
		if notice != "" {
			notices = append(notices, style.Render(notice))
		}
	}
	return notices
}

func (model *Model) renderMCPConnection(connection mcpcatalog.Connection) string {
	adapters := make([]string, len(connection.Adapters))
	for index, adapter := range connection.Adapters {
		adapters[index] = componentName(adapter)
	}
	return fmt.Sprintf(
		"  %s · %s\n    %s\n    %s · %s\n    %s",
		connection.ServerName,
		connection.Profile.Name,
		strings.Join(adapters, ", "),
		transportName(connection.Profile.Transport),
		authenticationRequirement(connection.Profile.Authentication.Kind),
		model.credentialPreviewStatus(connection),
	)
}

func (model *Model) credentialPreviewStatus(connection mcpcatalog.Connection) string {
	if connection.Profile.Authentication.Kind != mcpcatalog.AuthenticationAPIKey &&
		connection.Profile.ServiceCredential == nil {
		return "No credential instance is required."
	}
	choice := model.mcpChoices[connection.ServerID]
	if choice != nil && choice.credentialInstanceID != "" {
		for _, instance := range model.credentialInstances.All() {
			if instance.ID == choice.credentialInstanceID {
				return fmt.Sprintf(
					"Credential instance: %s (%s); secret value remains external.",
					instance.Name,
					instance.ID,
				)
			}
		}
		return "Credential instance selected; secret value remains external."
	}
	return "Credential instance is not selected."
}

func transportName(transport mcpcatalog.Transport) string {
	if transport == mcpcatalog.TransportStreamableHTTP {
		return "Streamable HTTP"
	}
	return "stdio"
}

func authenticationRequirement(kind mcpcatalog.AuthenticationKind) string {
	if kind == mcpcatalog.AuthenticationAPIKey {
		return "API key required"
	}
	return "No API key required"
}
