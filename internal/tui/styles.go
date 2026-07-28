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
			"When safe apply is available, one confirmation applies the reviewed changes as one transaction.\nSecret values are resolved only during final Apply and never shown in the interface.",
		),
	}, "\n")
}
