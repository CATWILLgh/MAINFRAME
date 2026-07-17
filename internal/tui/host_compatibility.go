package tui

import (
	"fmt"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

const maxDisplayedVersionBytes = 64
const unrecognizedVersion = "unrecognized"

func targetSelectable(target lifecycle.Target) bool {
	return target.HostCompatibility == nil ||
		target.HostCompatibility.Status == hostcompatibility.StatusSatisfied
}

func selectableSelection(
	targets []lifecycle.Target,
	selected []domain.ComponentID,
) []domain.ComponentID {
	available := make(map[domain.ComponentID]bool, len(targets))
	for _, target := range targets {
		available[target.ID] = targetSelectable(target)
	}
	result := make([]domain.ComponentID, 0, len(selected))
	for _, component := range selected {
		if available[component] {
			result = append(result, component)
		}
	}
	return result
}

func unavailableTargetsView(targets []lifecycle.Target) string {
	lines := []string{headingStyle.Render("Unavailable environments")}
	for _, target := range targets {
		if targetSelectable(target) {
			continue
		}
		lines = append(lines, "  "+compatibilityMessage(target))
	}
	if len(lines) == 1 {
		return ""
	}
	return strings.Join(lines, "\n")
}

func compatibilityMessage(target lifecycle.Target) string {
	name := componentName(target.ID)
	compatibility := target.HostCompatibility
	switch compatibility.Status {
	case hostcompatibility.StatusMissing:
		return name + " — required application is not installed"
	case hostcompatibility.StatusIncompatible:
		return fmt.Sprintf(
			"%s — installed version %s is not supported; supported: %s",
			name,
			displayVersions(compatibility.DetectedVersions),
			displayVersions(compatibility.ExpectedVersions),
		)
	default:
		return name + " — application could not be checked safely"
	}
}

func displayVersions(versions []string) string {
	display := make([]string, 0, len(versions))
	for _, version := range versions {
		if safeTerminalText(version, maxDisplayedVersionBytes) {
			display = append(display, version)
		} else {
			display = append(display, unrecognizedVersion)
		}
	}
	if len(display) == 0 {
		return unrecognizedVersion
	}
	return strings.Join(display, ", ")
}

func safeTerminalText(value string, maxBytes int) bool {
	if value == "" || len(value) > maxBytes {
		return false
	}
	for _, character := range value {
		if character < 0x20 || character > 0x7e {
			return false
		}
	}
	return true
}
