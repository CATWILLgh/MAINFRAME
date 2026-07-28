package tui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func configurationStatus(resources []lifecycle.ConfigurationResource) string {
	if len(resources) == 0 {
		return ""
	}
	counts := make(map[lifecycle.ConfigurationStatus]int)
	manualActions := 0
	for _, resource := range resources {
		if resource.Reason == lifecycle.ConfigurationManualActionRequired {
			manualActions++
			continue
		}
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
	if manualActions > 0 {
		parts = append(
			parts,
			countLabel(manualActions, "manual action", "manual actions"),
		)
	}
	if len(parts) == 0 {
		return " · configuration ready"
	}
	return " · configuration " + strings.Join(parts, ", ")
}

func renderConfigurationPlan(plan configuration.Plan) string {
	lines := []string{headingStyle.Render("Configuration plan")}
	if len(plan.Changes) == 0 && len(plan.Issues) == 0 &&
		len(plan.ManualActions) == 0 && len(plan.Notices) == 0 {
		return strings.Join(
			append(lines, mutedStyle.Render("No configuration changes.")),
			"\n",
		)
	}
	changes := append([]configuration.Change(nil), plan.Changes...)
	issues := append([]configuration.Issue(nil), plan.Issues...)
	sortConfigurationChanges(changes)
	sortConfigurationIssues(issues)
	if len(changes) > 0 {
		lines = append(lines, headingStyle.Render(fmt.Sprintf("Changes · %d", len(changes))))
	}
	for _, change := range changes {
		lines = append(lines, renderConfigurationChange(change))
	}
	if len(issues) > 0 {
		lines = append(lines, headingStyle.Render(fmt.Sprintf("Issues · %d", len(issues))))
	}
	for _, issue := range issues {
		lines = append(lines, renderConfigurationIssue(issue))
	}
	if len(plan.ManualActions) > 0 {
		lines = append(
			lines,
			headingStyle.Render(
				fmt.Sprintf("Manual actions · %d", len(plan.ManualActions)),
			),
		)
	}
	for _, action := range plan.ManualActions {
		lines = append(lines, renderManualAction(action))
	}
	if len(plan.Notices) > 0 {
		lines = append(
			lines,
			headingStyle.Render(fmt.Sprintf("Notices · %d", len(plan.Notices))),
		)
	}
	for _, notice := range plan.Notices {
		lines = append(lines, renderConfigurationNotice(notice))
	}
	return strings.Join(lines, "\n")
}

func renderManualAction(action configuration.ManualAction) string {
	switch action.Kind {
	case configuration.ManualActionCodexHookTrust:
		return "  •  Review MAINFRAME hooks in Codex with /hooks"
	default:
		return "  •  Complete the external configuration step"
	}
}

func renderConfigurationNotice(notice configuration.Notice) string {
	switch notice.Reason {
	case configuration.ExternalStateUnavailable:
		return "  !  Codex is unavailable; hook trust was not inspected"
	case configuration.ExternalInspectionFailed:
		return "  !  Codex hook trust inspection failed"
	case configuration.ManualActionUnverified:
		return fmt.Sprintf(
			"  !  %s activation remains manual and was not verified",
			componentName(notice.ComponentID),
		)
	default:
		return "  !  External configuration state was not inspected"
	}
}

func renderConfigurationChange(change configuration.Change) string {
	parts := []string{
		configurationChangeName(change.Kind),
		componentName(change.ComponentID),
		change.ResourceID,
	}
	scope := "configuration"
	if change.UnitID != "" {
		parts = append(parts, change.UnitID)
		scope = "configuration + ownership registry"
	}
	parts = append(parts, scope)
	return fmt.Sprintf(
		"  %s  %s",
		configurationChangeGlyph(change.Kind),
		strings.Join(parts, " · "),
	)
}

func configurationChangeName(kind configuration.ChangeKind) string {
	if kind == configuration.ChangeRelinquish {
		return "stop managing"
	}
	return string(kind)
}

func renderConfigurationIssue(issue configuration.Issue) string {
	parts := []string{
		configurationIssueName(issue.Kind),
		componentName(issue.ComponentID),
		issue.ResourceID,
	}
	if issue.UnitID != "" {
		parts = append(parts, issue.UnitID)
	}
	parts = append(parts, configurationReasonName(issue.Reason))
	return "  !  " + strings.Join(parts, " · ")
}

func sortConfigurationChanges(changes []configuration.Change) {
	sort.Slice(changes, func(left, right int) bool {
		a, b := changes[left], changes[right]
		if a.ResourceID != b.ResourceID {
			return a.ResourceID < b.ResourceID
		}
		if a.UnitID != b.UnitID {
			return a.UnitID < b.UnitID
		}
		return a.Kind < b.Kind
	})
}

func sortConfigurationIssues(issues []configuration.Issue) {
	sort.Slice(issues, func(left, right int) bool {
		a, b := issues[left], issues[right]
		if a.ResourceID != b.ResourceID {
			return a.ResourceID < b.ResourceID
		}
		if a.UnitID != b.UnitID {
			return a.UnitID < b.UnitID
		}
		return a.Kind < b.Kind
	})
}

func configurationChangeGlyph(kind configuration.ChangeKind) string {
	switch kind {
	case configuration.ChangeAdd:
		return "+"
	case configuration.ChangeRemove:
		return "−"
	case configuration.ChangeRelinquish:
		return "↪"
	default:
		return "~"
	}
}

func configurationIssueName(kind configuration.IssueKind) string {
	switch kind {
	case configuration.IssueAttention:
		return "needs attention"
	case configuration.IssueNotAssessed:
		return "not assessed"
	case configuration.IssueRemovalUnsupported:
		return "removal unsupported"
	case configuration.IssuePlanningUnavailable:
		return "planning unavailable"
	default:
		return "unknown issue"
	}
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
	case lifecycle.ConfigurationJSONFieldsMatch:
		return "owned fields match"
	case lifecycle.ConfigurationJSONFieldsDrifted:
		return "owned fields differ"
	case lifecycle.ConfigurationJSONDocumentInvalid:
		return "JSON document is invalid"
	case lifecycle.ConfigurationExternalStateSatisfied:
		return "external state is ready"
	case lifecycle.ConfigurationManualActionRequired:
		return "manual action is required"
	case lifecycle.ConfigurationExternalStateUnavailable:
		return "external state is unavailable"
	case lifecycle.ConfigurationExternalInspectionFailed:
		return "external inspection failed"
	default:
		return "unknown reason"
	}
}

func countLabel(count int, singular, plural string) string {
	label := plural
	if count == 1 {
		label = singular
	}
	return fmt.Sprintf("%d %s", count, label)
}
