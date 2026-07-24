package lifecycle

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

func (service Service) diagnosticsRemovalComponents(
	selected []domain.ComponentID,
	preserved []domain.ComponentID,
) []domain.ComponentID {
	selectedSet := componentSet(selected)
	preservedSet := componentSet(preserved)
	var result []domain.ComponentID
	for _, component := range service.observed.Components {
		if !selectable(component.ID) ||
			selectedSet[component.ID] ||
			preservedSet[component.ID] ||
			!component.Managed() {
			continue
		}
		result = append(result, component.ID)
	}
	return result
}

func componentSet(components []domain.ComponentID) map[domain.ComponentID]bool {
	result := make(map[domain.ComponentID]bool, len(components))
	for _, component := range components {
		result[component] = true
	}
	return result
}
