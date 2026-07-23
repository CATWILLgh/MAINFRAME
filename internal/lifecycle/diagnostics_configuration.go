package lifecycle

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const diagnosticsSchemaVersion = 1

func diagnosticsExactDocuments(
	plan diagnostics.Plan,
	resources []releasecontract.Resource,
) ([]configuration.ExactJSONDocument, bool, error) {
	if len(plan.Intents) == 0 {
		return nil, false, nil
	}
	byComponent := exactDiagnosticsResourcesByComponent(resources)
	documents := make([]configuration.ExactJSONDocument, 0, len(plan.Intents))
	missing := 0
	for _, intent := range plan.Intents {
		matches := byComponent[intent.ComponentID]
		if len(matches) == 0 {
			missing++
			continue
		}
		if len(matches) != 1 {
			return nil, false, fmt.Errorf(
				"diagnostics resource for %q is ambiguous",
				intent.ComponentID,
			)
		}
		documents = append(documents, exactDiagnosticsDocument(matches[0], intent))
	}
	if missing == len(plan.Intents) {
		return nil, false, nil
	}
	if missing > 0 {
		return nil, false, fmt.Errorf("diagnostics resource scope is incomplete")
	}
	return documents, true, nil
}

func exactDiagnosticsResourcesByComponent(
	resources []releasecontract.Resource,
) map[domain.ComponentID][]releasecontract.Resource {
	result := make(map[domain.ComponentID][]releasecontract.Resource)
	for _, resource := range resources {
		if resource.Strategy != releasecontract.StrategyExactJSONDocument ||
			!configuration.IsExactDiagnosticsTarget(resource.Target) {
			continue
		}
		result[resource.ComponentID] = append(
			result[resource.ComponentID],
			resource,
		)
	}
	return result
}

func exactDiagnosticsDocument(
	resource releasecontract.Resource,
	intent diagnostics.Intent,
) configuration.ExactJSONDocument {
	if !intent.Events && !intent.Feedback {
		return configuration.ExactJSONDocument{
			ResourceID:  resource.ID,
			Disposition: configuration.ExactJSONAbsent,
		}
	}
	return configuration.ExactJSONDocument{
		ResourceID:  resource.ID,
		Disposition: configuration.ExactJSONPresent,
		Document: []byte(fmt.Sprintf(
			`{"events":%t,"feedback":%t,"schema_version":%d}`,
			intent.Events,
			intent.Feedback,
			diagnosticsSchemaVersion,
		)),
	}
}

func mergeConfigurationPlans(plans ...configuration.Plan) configuration.Plan {
	result := configuration.Plan{}
	for _, plan := range plans {
		result.Changes = append(result.Changes, plan.Changes...)
		result.Issues = append(result.Issues, plan.Issues...)
		result.ManualActions = append(
			result.ManualActions,
			plan.ManualActions...,
		)
		result.Notices = append(result.Notices, plan.Notices...)
	}
	sort.Slice(result.Changes, func(left, right int) bool {
		return configurationChangeKey(result.Changes[left]) <
			configurationChangeKey(result.Changes[right])
	})
	sort.Slice(result.Issues, func(left, right int) bool {
		return configurationIssueKey(result.Issues[left]) <
			configurationIssueKey(result.Issues[right])
	})
	sort.Slice(result.ManualActions, func(left, right int) bool {
		return configurationManualKey(result.ManualActions[left]) <
			configurationManualKey(result.ManualActions[right])
	})
	sort.Slice(result.Notices, func(left, right int) bool {
		return configurationNoticeKey(result.Notices[left]) <
			configurationNoticeKey(result.Notices[right])
	})
	return result
}

func configurationChangeKey(change configuration.Change) string {
	return string(change.ComponentID) + "\x00" + change.ResourceID + "\x00" +
		change.UnitID + "\x00" + string(change.Kind)
}

func configurationIssueKey(issue configuration.Issue) string {
	return string(issue.ComponentID) + "\x00" + issue.ResourceID + "\x00" +
		issue.UnitID + "\x00" + string(issue.Kind) + "\x00" +
		string(issue.Reason)
}

func configurationManualKey(action configuration.ManualAction) string {
	return string(action.ComponentID) + "\x00" + action.ResourceID + "\x00" +
		string(action.Kind) + "\x00" + string(action.Reason)
}

func configurationNoticeKey(notice configuration.Notice) string {
	return string(notice.ComponentID) + "\x00" + notice.ResourceID + "\x00" +
		string(notice.Reason)
}
