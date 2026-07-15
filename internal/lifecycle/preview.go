package lifecycle

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

type TargetStatus string

const (
	StatusAbsent    TargetStatus = "absent"
	StatusManaged   TargetStatus = "managed"
	StatusAttention TargetStatus = "attention"
)

var visibleTargets = []domain.ComponentID{
	domain.ComponentClaudeCode,
	domain.ComponentCodex,
	domain.ComponentOpenCode,
}

type Target struct {
	ID       domain.ComponentID
	Status   TargetStatus
	Selected bool
}

type Service struct {
	planner       plan.Planner
	observed      domain.ObservedState
	desiredCounts map[domain.ComponentID]int
}

func New(model installmodel.Model, observed domain.ObservedState) (Service, error) {
	planner := plan.New(model.Catalog())
	if _, err := planner.Plan(domain.PlanRequest{Observed: observed}); err != nil {
		return Service{}, fmt.Errorf("validate observed state: %w", err)
	}
	return Service{
		planner:       planner,
		observed:      cloneObserved(observed),
		desiredCounts: countDesiredArtifacts(model),
	}, nil
}

func (service Service) Targets() []Target {
	observed := make(map[domain.ComponentID]domain.ObservedComponent)
	for _, component := range service.observed.Components {
		observed[component.ID] = component
	}
	targets := make([]Target, 0, len(visibleTargets))
	for _, id := range visibleTargets {
		component, exists := observed[id]
		targets = append(targets, Target{
			ID:       id,
			Status:   service.status(id, component, exists),
			Selected: exists,
		})
	}
	return targets
}

func (service Service) Plan(components []domain.ComponentID) (domain.Plan, error) {
	seen := make(map[domain.ComponentID]bool, len(components))
	for _, id := range components {
		if !selectable(id) {
			return domain.Plan{}, fmt.Errorf("component %q is not selectable", id)
		}
		if seen[id] {
			return domain.Plan{}, fmt.Errorf("duplicate selected component %q", id)
		}
		seen[id] = true
	}
	return service.planner.Plan(domain.PlanRequest{
		Desired:  domain.DesiredState{Components: append([]domain.ComponentID(nil), components...)},
		Observed: cloneObserved(service.observed),
	})
}

func (service Service) status(
	id domain.ComponentID,
	component domain.ObservedComponent,
	exists bool,
) TargetStatus {
	if !exists {
		return StatusAbsent
	}
	if len(component.Artifacts) < service.desiredCounts[id] {
		return StatusAttention
	}
	for _, artifact := range component.Artifacts {
		if artifact.Ownership != domain.OwnershipManagedExact {
			return StatusAttention
		}
	}
	return StatusManaged
}

func selectable(id domain.ComponentID) bool {
	for _, candidate := range visibleTargets {
		if id == candidate {
			return true
		}
	}
	return false
}

func countDesiredArtifacts(model installmodel.Model) map[domain.ComponentID]int {
	counts := make(map[domain.ComponentID]int)
	for _, artifact := range model.Artifacts() {
		if !artifact.LegacyOnly {
			counts[artifact.ComponentID]++
		}
	}
	return counts
}

func cloneObserved(observed domain.ObservedState) domain.ObservedState {
	clone := domain.ObservedState{
		Components: make([]domain.ObservedComponent, len(observed.Components)),
	}
	for index, component := range observed.Components {
		clone.Components[index] = domain.ObservedComponent{
			ID:        component.ID,
			Artifacts: append([]domain.Artifact(nil), component.Artifacts...),
		}
	}
	return clone
}
