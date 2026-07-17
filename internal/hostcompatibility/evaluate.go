package hostcompatibility

import (
	"slices"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type rowAssessment struct {
	status   Status
	detected []string
	expected []string
}

func Evaluate(
	requirements []releasecontract.HostRequirement,
	inventory ApplicationInventory,
) []Assessment {
	byComponent := make(map[domain.ComponentID][]rowAssessment)
	for _, requirement := range requirements {
		row := evaluateRow(requirement, inventory)
		byComponent[requirement.ComponentID] = append(byComponent[requirement.ComponentID], row)
	}

	components := make([]domain.ComponentID, 0, len(byComponent))
	for component := range byComponent {
		components = append(components, component)
	}
	sort.Slice(components, func(left, right int) bool { return components[left] < components[right] })

	assessments := make([]Assessment, 0, len(components))
	for _, component := range components {
		assessments = append(assessments, aggregateRows(component, byComponent[component]))
	}
	return assessments
}

func evaluateRow(
	requirement releasecontract.HostRequirement,
	inventory ApplicationInventory,
) rowAssessment {
	expected := sortedUnique(requirement.ExactVersions)
	if requirement.Kind != releasecontract.HostRequirementDarwinApplicationBundleV1 {
		return rowAssessment{status: StatusUnavailable, expected: expected}
	}

	var detected []string
	hasExact := false
	hasUnsupported := false
	for _, application := range inventory.Applications {
		if application.BundleIdentifier != requirement.BundleIdentifier {
			continue
		}
		detected = append(detected, application.Version)
		if slices.Contains(expected, application.Version) {
			hasExact = true
		} else {
			hasUnsupported = true
		}
	}
	detected = sortedUnique(detected)
	if hasExact && !hasUnsupported {
		return rowAssessment{status: StatusSatisfied, detected: detected, expected: expected}
	}
	if hasExact && hasUnsupported {
		return rowAssessment{status: StatusIncompatible, detected: detected, expected: expected}
	}
	if !inventory.Available || !inventory.Complete {
		return rowAssessment{status: StatusUnavailable, detected: detected, expected: expected}
	}
	if len(detected) > 0 {
		return rowAssessment{status: StatusIncompatible, detected: detected, expected: expected}
	}
	return rowAssessment{status: StatusMissing, expected: expected}
}

func aggregateRows(component domain.ComponentID, rows []rowAssessment) Assessment {
	status := StatusSatisfied
	for _, row := range rows {
		status = lessCompatible(status, row.status)
	}

	var detected []string
	var expected []string
	for _, row := range rows {
		expected = append(expected, row.expected...)
		if status == StatusSatisfied || row.status != StatusSatisfied {
			detected = append(detected, row.detected...)
		}
	}
	return Assessment{
		ComponentID:      component,
		Status:           status,
		DetectedVersions: sortedUnique(detected),
		ExpectedVersions: sortedUnique(expected),
	}
}

func lessCompatible(current, candidate Status) Status {
	priority := map[Status]int{
		StatusSatisfied: 0, StatusMissing: 1, StatusIncompatible: 2, StatusUnavailable: 3,
	}
	if priority[candidate] > priority[current] {
		return candidate
	}
	return current
}

func sortedUnique(values []string) []string {
	result := slices.Clone(values)
	slices.Sort(result)
	return slices.Compact(result)
}
