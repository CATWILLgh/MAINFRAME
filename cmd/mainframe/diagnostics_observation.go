package main

import (
	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type diagnosticsObservationScope struct {
	reviewed   bool
	configured bool
	components map[domain.ComponentID]bool
}

func diagnosticsObservationScopeFor(
	request application.Request,
) diagnosticsObservationScope {
	components := make(map[domain.ComponentID]bool, len(request.Components))
	for _, component := range request.Components {
		components[component] = true
	}
	return diagnosticsObservationScope{
		reviewed:   true,
		configured: request.Diagnostics.Configured,
		components: components,
	}
}

func resourcesForDiagnosticsObservation(
	resources []releasecontract.Resource,
	scope diagnosticsObservationScope,
	observed domain.ObservedState,
) []releasecontract.Resource {
	managed := managedObservedComponents(observed)
	filtered := make([]releasecontract.Resource, 0, len(resources))
	for _, resource := range resources {
		if resource.Strategy == releasecontract.StrategyExactJSONDocument &&
			!diagnosticsResourceInScope(resource.ComponentID, scope, managed) {
			continue
		}
		filtered = append(filtered, resource)
	}
	return filtered
}

func diagnosticsResourceInScope(
	component domain.ComponentID,
	scope diagnosticsObservationScope,
	managed map[domain.ComponentID]bool,
) bool {
	if !scope.reviewed {
		return false
	}
	if scope.configured && scope.components[component] {
		return true
	}
	return !scope.components[component] && managed[component]
}

func managedObservedComponents(
	observed domain.ObservedState,
) map[domain.ComponentID]bool {
	result := make(map[domain.ComponentID]bool)
	for _, component := range observed.Components {
		if component.Managed() {
			result[component.ID] = true
		}
	}
	return result
}
