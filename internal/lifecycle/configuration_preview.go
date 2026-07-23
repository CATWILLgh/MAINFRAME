package lifecycle

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
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
	observations = externalObservationsForInventory(
		resources,
		observations,
		observed,
	)
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

func NewWithInspections(
	model installmodel.Model,
	observed domain.ObservedState,
	configurationInspection configuration.Inspection,
	mcpInspection mcpconfiguration.Inspection,
) (Service, error) {
	service, err := NewWithInspection(model, observed, configurationInspection)
	if err != nil {
		return Service{}, err
	}
	service.mcpInspection = &mcpInspection
	return service, nil
}

func externalObservationsForInventory(
	resources []releasecontract.Resource,
	observations []configuration.Observation,
	observed domain.ObservedState,
) []configuration.Observation {
	result := append([]configuration.Observation(nil), observations...)
	resourceByID := make(map[string]releasecontract.Resource, len(resources))
	for _, resource := range resources {
		resourceByID[resource.ID] = resource
	}
	for index, observation := range result {
		resource := resourceByID[observation.ResourceID]
		if resource.ExternalState == nil ||
			observation.Status != configuration.Ready ||
			observedTargetTrustedExact(
				observed,
				resource.ComponentID,
				resource.Target,
			) {
			continue
		}
		result[index].Status = configuration.NeedsChange
		result[index].Reason = configuration.ManualActionRequired
	}
	return result
}

func (service Service) Preview(request PreviewRequest) (Preview, error) {
	diagnosticsPlan, err := diagnostics.Build(request.Components, request.Diagnostics)
	if err != nil {
		return Preview{}, fmt.Errorf("plan diagnostics: %w", err)
	}
	filesystem, err := service.Plan(request.Components)
	if err != nil {
		return Preview{}, err
	}
	preservationRoots := service.preservationRoots(request.Components)
	mcpPlan := mcpconfiguration.Plan{}
	if service.mcpInspection != nil {
		mcpPlan, err = service.mcpInspection.PlanWithPreservation(
			request.Components,
			preservationRoots,
			request.MCPSelections,
		)
		if err != nil {
			return Preview{}, fmt.Errorf("plan MCP configuration: %w", err)
		}
	}
	configurationPlan, err := service.planManagedConfiguration(
		request.Components,
		preservationRoots,
	)
	if err != nil {
		return Preview{}, err
	}
	exactPlan, executable, err := service.planDiagnosticsConfiguration(
		diagnosticsPlan,
	)
	if err != nil {
		return Preview{}, err
	}
	if executable {
		configurationPlan = mergeConfigurationPlans(
			configurationPlan,
			exactPlan,
		)
		diagnosticsPlan.Executable = true
	}
	return Preview{
		Filesystem:    filesystem,
		Configuration: configurationPlan,
		MCP:           mcpPlan,
		Diagnostics:   diagnosticsPlan,
	}, nil
}

func (service Service) planManagedConfiguration(
	components []domain.ComponentID,
	preservationRoots []domain.ComponentID,
) (configuration.Plan, error) {
	preserved := service.configurationComponents(preservationRoots)
	if service.configurationInspection == nil {
		return filterConfigurationPlan(
			service.configurationFallback,
			preserved,
		), nil
	}
	included := service.configurationComponents(components)
	plan, err := service.configurationInspection.PlanWithPreservation(
		included,
		preserved,
	)
	if err != nil {
		return configuration.Plan{}, fmt.Errorf("plan configuration: %w", err)
	}
	service.requireReviewAfterExternalTargetChange(&plan, included)
	return plan, nil
}

func (service Service) planDiagnosticsConfiguration(
	plan diagnostics.Plan,
) (configuration.Plan, bool, error) {
	if service.configurationInspection == nil {
		return configuration.Plan{}, false, nil
	}
	documents, available, err := diagnosticsExactDocuments(
		plan,
		service.configurationInspection.Resources(),
	)
	if err != nil || !available {
		return configuration.Plan{}, false, err
	}
	exact, err := service.configurationInspection.PlanExactJSONDocuments(
		documents,
	)
	if err != nil {
		return configuration.Plan{}, false, fmt.Errorf(
			"plan diagnostics configuration: %w",
			err,
		)
	}
	return exact, true, nil
}

func (service Service) requireReviewAfterExternalTargetChange(
	plan *configuration.Plan,
	included []domain.ComponentID,
) {
	selected := make(map[domain.ComponentID]bool, len(included))
	for _, component := range included {
		selected[component] = true
	}
	observations := make(map[string]configuration.Observation)
	for _, observation := range service.configurationInspection.Observations() {
		observations[observation.ResourceID] = observation
	}
	for _, resource := range service.configurationInspection.Resources() {
		if resource.ExternalState == nil ||
			!selected[resource.ComponentID] ||
			observations[resource.ID].Status != configuration.Ready ||
			service.targetTrustedExact(resource.ComponentID, resource.Target) {
			continue
		}
		plan.ManualActions = append(
			plan.ManualActions,
			configuration.ManualAction{
				ResourceID:  resource.ID,
				ComponentID: resource.ComponentID,
				Kind:        configuration.ManualActionCodexHookTrust,
				Reason:      configuration.ManualActionRequired,
			},
		)
	}
	sort.Slice(plan.ManualActions, func(left, right int) bool {
		return plan.ManualActions[left].ResourceID <
			plan.ManualActions[right].ResourceID
	})
}

func (service Service) targetTrustedExact(
	componentID domain.ComponentID,
	target domain.Location,
) bool {
	return observedTargetTrustedExact(service.observed, componentID, target)
}

func observedTargetTrustedExact(
	observed domain.ObservedState,
	componentID domain.ComponentID,
	target domain.Location,
) bool {
	for _, component := range observed.Components {
		if component.ID != componentID {
			continue
		}
		for _, artifact := range component.Artifacts {
			if artifact.Location == target {
				return artifact.Ownership == domain.OwnershipManagedExact ||
					artifact.Ownership == domain.OwnershipExactAdoptable
			}
		}
	}
	return false
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
		ManualActions: append(
			[]configuration.ManualAction(nil),
			source.ManualActions...,
		),
		Notices: append([]configuration.Notice(nil), source.Notices...),
	}
}

func filterConfigurationPlan(
	source configuration.Plan,
	preserved []domain.ComponentID,
) configuration.Plan {
	if len(preserved) == 0 {
		return cloneConfigurationPlan(source)
	}
	blocked := make(map[domain.ComponentID]bool, len(preserved))
	for _, component := range preserved {
		blocked[component] = true
	}
	result := configuration.Plan{}
	for _, change := range source.Changes {
		if !blocked[change.ComponentID] {
			result.Changes = append(result.Changes, change)
		}
	}
	for _, issue := range source.Issues {
		if !blocked[issue.ComponentID] {
			result.Issues = append(result.Issues, issue)
		}
	}
	for _, action := range source.ManualActions {
		if !blocked[action.ComponentID] {
			result.ManualActions = append(result.ManualActions, action)
		}
	}
	for _, notice := range source.Notices {
		if !blocked[notice.ComponentID] {
			result.Notices = append(result.Notices, notice)
		}
	}
	return result
}
