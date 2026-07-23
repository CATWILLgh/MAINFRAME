package lifecycle

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func (service Service) status(
	id domain.ComponentID,
	observed map[domain.ComponentID]domain.ObservedComponent,
) TargetStatus {
	if observed[id].ID == "" {
		return StatusAbsent
	}
	for _, componentID := range service.dependencies[id] {
		expected := service.desiredCounts[componentID]
		if expected == 0 {
			continue
		}
		component, exists := observed[componentID]
		actual := 0
		for _, artifact := range component.Artifacts {
			if service.featureTargets[componentID][artifact.Location] {
				continue
			}
			actual++
			if artifact.Ownership != domain.OwnershipManagedExact {
				return StatusAttention
			}
		}
		if !exists || actual != expected {
			return StatusAttention
		}
	}
	return StatusManaged
}

func countDesiredArtifacts(model installmodel.Model) map[domain.ComponentID]int {
	counts := make(map[domain.ComponentID]int)
	for _, artifact := range model.Artifacts() {
		if !artifact.LegacyOnly && artifact.Feature == "" {
			counts[artifact.ComponentID]++
		}
	}
	return counts
}

func featureArtifactTargets(
	model installmodel.Model,
) map[domain.ComponentID]map[domain.Location]bool {
	targets := make(map[domain.ComponentID]map[domain.Location]bool)
	for _, artifact := range model.Artifacts() {
		if artifact.LegacyOnly || artifact.Feature == "" {
			continue
		}
		if targets[artifact.ComponentID] == nil {
			targets[artifact.ComponentID] = make(map[domain.Location]bool)
		}
		targets[artifact.ComponentID][artifact.Target] = true
	}
	return targets
}
