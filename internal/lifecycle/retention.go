package lifecycle

import (
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (service Service) retainedAdapters(selected []domain.ComponentID) []domain.ComponentID {
	retained := componentSet(service.preservationRoots(selected))
	for _, component := range service.unmanagedOmittedAdapters(selected) {
		retained[component] = true
	}
	return sortedComponentSet(retained)
}

func (service Service) configurationPreservationComponents(
	selected []domain.ComponentID,
) []domain.ComponentID {
	preserved := componentSet(service.configurationComponents(service.preservationRoots(selected)))
	for _, component := range service.unmanagedOmittedAdapters(selected) {
		preserved[component] = true
	}
	return sortedComponentSet(preserved)
}

func (service Service) unmanagedOmittedAdapters(
	selected []domain.ComponentID,
) []domain.ComponentID {
	selectedSet := componentSet(selected)
	observedByID := make(map[domain.ComponentID]domain.ObservedComponent, len(service.observed.Components))
	for _, component := range service.observed.Components {
		observedByID[component.ID] = component
	}
	var result []domain.ComponentID
	for _, target := range visibleTargets {
		if _, available := service.dependencies[target]; !available || selectedSet[target] {
			continue
		}
		observed, exists := observedByID[target]
		if exists && !observed.Managed() {
			result = append(result, target)
		}
	}
	return result
}

func sortedComponentSet(components map[domain.ComponentID]bool) []domain.ComponentID {
	result := make([]domain.ComponentID, 0, len(components))
	for component := range components {
		result = append(result, component)
	}
	sort.Slice(result, func(left, right int) bool {
		return result[left] < result[right]
	})
	return result
}
