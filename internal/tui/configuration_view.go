package tui

import (
	"fmt"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func configurationStatus(resources []lifecycle.ConfigurationResource) string {
	if len(resources) == 0 {
		return ""
	}
	counts := make(map[lifecycle.ConfigurationStatus]int)
	for _, resource := range resources {
		counts[resource.Status]++
	}
	parts := make([]string, 0, 3)
	if count := counts[lifecycle.ConfigurationNeedsChange]; count > 0 {
		parts = append(parts, countLabel(count, "change", "changes"))
	}
	if count := counts[lifecycle.ConfigurationAttention]; count > 0 {
		parts = append(parts, countLabel(count, "warning", "warnings"))
	}
	if count := counts[lifecycle.ConfigurationNotAssessed]; count > 0 {
		parts = append(parts, fmt.Sprintf("%d not assessed", count))
	}
	if len(parts) == 0 {
		return " · configuration ready"
	}
	return " · configuration " + strings.Join(parts, ", ")
}

func selectedConfiguration(
	targets []lifecycle.Target,
	selected []domain.ComponentID,
) []lifecycle.ConfigurationResource {
	resources := make([]lifecycle.ConfigurationResource, 0)
	seen := make(map[string]bool)
	for _, target := range targets {
		if contains(selected, target.ID) {
			for _, resource := range target.Configuration {
				if !seen[resource.ID] {
					resources = append(resources, resource)
					seen[resource.ID] = true
				}
			}
		}
	}
	return resources
}

func renderConfiguration(resources []lifecycle.ConfigurationResource) string {
	lines := []string{
		headingStyle.Render(fmt.Sprintf("Configuration status · %d", len(resources))),
	}
	for _, resource := range resources {
		lines = append(lines, fmt.Sprintf(
			"  %s  %s · %s · %s · %s",
			configurationGlyph(resource.Status),
			resource.ID,
			resource.Strategy,
			configurationStatusName(resource.Status),
			configurationReasonName(resource.Reason),
		))
	}
	return strings.Join(lines, "\n")
}

func configurationStatusName(status lifecycle.ConfigurationStatus) string {
	switch status {
	case lifecycle.ConfigurationReady:
		return "ready"
	case lifecycle.ConfigurationNeedsChange:
		return "needs change"
	case lifecycle.ConfigurationNotApplicable:
		return "not applicable"
	case lifecycle.ConfigurationAttention:
		return "needs attention"
	case lifecycle.ConfigurationNotAssessed:
		return "not assessed"
	default:
		return "unknown"
	}
}

func configurationReasonName(reason lifecycle.ConfigurationReason) string {
	switch reason {
	case lifecycle.ConfigurationResourceExists:
		return "file exists"
	case lifecycle.ConfigurationDirectoryExists:
		return "directory exists"
	case lifecycle.ConfigurationLinePresent:
		return "line is present"
	case lifecycle.ConfigurationResourceMissing:
		return "file is missing"
	case lifecycle.ConfigurationDirectoryMissing:
		return "directory is missing"
	case lifecycle.ConfigurationLineMissing:
		return "line is missing"
	case lifecycle.ConfigurationOptionalTargetMissing:
		return "optional file is absent"
	case lifecycle.ConfigurationSymbolicLink:
		return "symbolic link is not followed"
	case lifecycle.ConfigurationWrongKind:
		return "unexpected file type"
	case lifecycle.ConfigurationInspectionFailed:
		return "inspection failed"
	case lifecycle.ConfigurationObservationUnsupported:
		return "observation is not implemented"
	default:
		return "unknown reason"
	}
}

func configurationGlyph(status lifecycle.ConfigurationStatus) string {
	switch status {
	case lifecycle.ConfigurationReady:
		return "✓"
	case lifecycle.ConfigurationNeedsChange:
		return "+"
	case lifecycle.ConfigurationNotApplicable:
		return "·"
	case lifecycle.ConfigurationAttention:
		return "!"
	default:
		return "?"
	}
}

func countLabel(count int, singular, plural string) string {
	label := plural
	if count == 1 {
		label = singular
	}
	return fmt.Sprintf("%d %s", count, label)
}
