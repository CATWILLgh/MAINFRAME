package lifecycle

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func NewWithInspection(
	model installmodel.Model,
	observed domain.ObservedState,
	inspection configuration.Inspection,
) (Service, error) {
	resources := inspection.Resources()
	observations := inspection.Observations()
	if err := configuration.Validate(resources, observations); err != nil {
		return Service{}, fmt.Errorf("validate configuration inspection: %w", err)
	}
	indexed := make(map[string]configuration.Observation, len(observations))
	for _, observation := range observations {
		indexed[observation.ResourceID] = observation
	}
	service, err := newService(model, observed, resources, indexed)
	if err != nil {
		return Service{}, err
	}
	service.configurationInspection = &inspection
	return service, nil
}

func (service Service) Preview(components []domain.ComponentID) (Preview, error) {
	filesystem, err := service.Plan(components)
	if err != nil {
		return Preview{}, err
	}
	if service.configurationInspection == nil {
		return Preview{
			Filesystem:    filesystem,
			Configuration: cloneConfigurationPlan(service.configurationFallback),
		}, nil
	}
	included := service.configurationComponents(components)
	configurationPlan, err := service.configurationInspection.Plan(included)
	if err != nil {
		return Preview{}, fmt.Errorf("plan configuration: %w", err)
	}
	return Preview{
		Filesystem:    filesystem,
		Configuration: configurationPlan,
	}, nil
}

func (service Service) configurationComponents(
	selected []domain.ComponentID,
) []domain.ComponentID {
	seen := make(map[domain.ComponentID]bool)
	for _, visible := range selected {
		for _, component := range service.dependencies[visible] {
			seen[component] = true
		}
	}
	result := make([]domain.ComponentID, 0, len(seen))
	for component := range seen {
		result = append(result, component)
	}
	sort.Slice(result, func(left, right int) bool {
		return result[left] < result[right]
	})
	return result
}

func unavailableConfigurationPlan(
	resources []releasecontract.Resource,
	observations map[string]configuration.Observation,
) configuration.Plan {
	issues := make([]configuration.Issue, 0, len(resources))
	for _, resource := range resources {
		issues = append(issues, configuration.Issue{
			ResourceID:  resource.ID,
			ComponentID: resource.ComponentID,
			Kind:        configuration.IssuePlanningUnavailable,
			Reason:      observations[resource.ID].Reason,
		})
	}
	sort.Slice(issues, func(left, right int) bool {
		return issues[left].ResourceID < issues[right].ResourceID
	})
	return configuration.Plan{Issues: issues}
}

func cloneConfigurationPlan(source configuration.Plan) configuration.Plan {
	return configuration.Plan{
		Changes: append([]configuration.Change(nil), source.Changes...),
		Issues:  append([]configuration.Issue(nil), source.Issues...),
	}
}
