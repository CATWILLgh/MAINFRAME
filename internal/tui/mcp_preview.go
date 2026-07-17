package tui

import (
	"fmt"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func renderMCPPreview(preview mcpcatalog.OnboardingPreview) string {
	lines := []string{headingStyle.Render("MCP onboarding choices")}
	if len(preview.Connections) == 0 {
		lines = append(lines, mutedStyle.Render("No MCP integrations selected."))
	} else {
		for _, connection := range preview.Connections {
			lines = append(lines, renderMCPConnection(connection))
		}
	}
	lines = append(lines, mutedStyle.Render(
		"Read-only choice. Configuration and credentials are not changed.",
	))
	return strings.Join(lines, "\n")
}

func renderMCPConfigurationPlan(plan mcpconfiguration.Plan) string {
	lines := []string{headingStyle.Render("MCP configuration plan")}
	if len(plan.Intents) == 0 {
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

func renderMCPConnection(connection mcpcatalog.Connection) string {
	adapters := make([]string, len(connection.Adapters))
	for index, adapter := range connection.Adapters {
		adapters[index] = componentName(adapter)
	}
	return fmt.Sprintf(
		"  %s · %s\n    %s\n    %s · %s",
		connection.ServerName,
		connection.Profile.Name,
		strings.Join(adapters, ", "),
		transportName(connection.Profile.Transport),
		authenticationRequirement(connection.Profile.Authentication.Kind),
	)
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
