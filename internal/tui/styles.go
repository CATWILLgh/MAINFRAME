package tui

import (
	"strings"

	"charm.land/lipgloss/v2"
)

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

func header() string {
	return strings.Join([]string{
		brandStyle.Render("MAINFRAME"),
		bannerStyle.Render("PLAN BEFORE APPLY"),
		mutedStyle.Render(
			"Configure your choices first.\nNothing changes until you review and confirm the complete plan.",
		),
		mutedStyle.Render(
			"Only a confirmed credential-only plan can be applied in this build.\nEnvironment, MCP, and DEV changes remain preview-only.",
		),
	}, "\n")
}
