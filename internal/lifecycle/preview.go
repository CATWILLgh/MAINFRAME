package lifecycle

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
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
	domain.ComponentAntigravity2,
}

type Target struct {
	ID            domain.ComponentID
	Status        TargetStatus
	Selected      bool
	Configuration []ConfigurationResource
}

type ConfigurationStatus = configuration.Status
type ConfigurationReason = configuration.Reason

const (
	ConfigurationReady         = configuration.Ready
	ConfigurationNeedsChange   = configuration.NeedsChange
	ConfigurationNotApplicable = configuration.NotApplicable
	ConfigurationAttention     = configuration.Attention
	ConfigurationNotAssessed   = configuration.NotAssessed

	ConfigurationResourceExists         = configuration.ResourceExists
	ConfigurationDirectoryExists        = configuration.DirectoryExists
	ConfigurationLinePresent            = configuration.LinePresent
	ConfigurationResourceMissing        = configuration.ResourceMissing
	ConfigurationDirectoryMissing       = configuration.DirectoryMissing
	ConfigurationLineMissing            = configuration.LineMissing
	ConfigurationOptionalTargetMissing  = configuration.OptionalTargetMissing
	ConfigurationSymbolicLink           = configuration.SymbolicLink
	ConfigurationWrongKind              = configuration.WrongKind
	ConfigurationInspectionFailed       = configuration.InspectionFailed
	ConfigurationObservationUnsupported = configuration.ObservationUnsupported
	ConfigurationJSONFieldsMatch        = configuration.JSONFieldsMatch
	ConfigurationJSONFieldsDrifted      = configuration.JSONFieldsDrifted
	ConfigurationJSONDocumentInvalid    = configuration.JSONDocumentInvalid
)

type ConfigurationResource struct {
	ID       string
	Strategy releasecontract.ResourceStrategy
	Status   ConfigurationStatus
	Reason   ConfigurationReason
}

type Service struct {
	planner       plan.Planner
	observed      domain.ObservedState
	desiredCounts map[domain.ComponentID]int
	dependencies  map[domain.ComponentID][]domain.ComponentID
	configuration map[domain.ComponentID][]ConfigurationResource
}

func New(model installmodel.Model, observed domain.ObservedState) (Service, error) {
	return NewWithResources(model, observed, nil)
}

func NewWithResources(
	model installmodel.Model,
	observed domain.ObservedState,
	resources []releasecontract.Resource,
) (Service, error) {
	observations := make([]configuration.Observation, 0, len(resources))
	for _, resource := range resources {
		if resource.Observation != releasecontract.SupportUnimplemented {
			return Service{}, fmt.Errorf("configuration resource %q requires an observation", resource.ID)
		}
		observations = append(observations, configuration.Observation{
			ResourceID: resource.ID, ComponentID: resource.ComponentID,
			Status: configuration.NotAssessed, Reason: configuration.ObservationUnsupported,
		})
	}
	return NewWithConfiguration(model, observed, resources, observations)
}

func NewWithConfiguration(
	model installmodel.Model,
	observed domain.ObservedState,
	resources []releasecontract.Resource,
	observations []configuration.Observation,
) (Service, error) {
	if err := configuration.Validate(resources, observations); err != nil {
		return Service{}, fmt.Errorf("validate configuration observations: %w", err)
	}
	indexed := make(map[string]configuration.Observation, len(observations))
	for _, observation := range observations {
		indexed[observation.ResourceID] = observation
	}
	return newService(model, observed, resources, indexed)
}

func newService(
	model installmodel.Model,
	observed domain.ObservedState,
	resources []releasecontract.Resource,
	observations map[string]configuration.Observation,
) (Service, error) {
	planner := plan.New(model.Catalog())
	if _, err := planner.Plan(domain.PlanRequest{Observed: observed}); err != nil {
		return Service{}, fmt.Errorf("validate observed state: %w", err)
	}
	dependencies, err := visibleDependencyClosures(model)
	if err != nil {
		return Service{}, err
	}
	configurationInventory, err := configurationInventory(model, resources, dependencies, observations)
	if err != nil {
		return Service{}, err
	}
	return Service{
		planner:       planner,
		observed:      cloneObserved(observed),
		desiredCounts: countDesiredArtifacts(model),
		dependencies:  dependencies,
		configuration: configurationInventory,
	}, nil
}

func (service Service) Targets() []Target {
	observed := make(map[domain.ComponentID]domain.ObservedComponent)
	for _, component := range service.observed.Components {
		observed[component.ID] = component
	}
	targets := make([]Target, 0, len(visibleTargets))
	for _, id := range visibleTargets {
		targets = append(targets, Target{
			ID:            id,
			Status:        service.status(id, observed),
			Selected:      observed[id].ID != "",
			Configuration: append([]ConfigurationResource(nil), service.configuration[id]...),
		})
	}
	return targets
}

func configurationInventory(
	model installmodel.Model,
	resources []releasecontract.Resource,
	dependencies map[domain.ComponentID][]domain.ComponentID,
	observations map[string]configuration.Observation,
) (map[domain.ComponentID][]ConfigurationResource, error) {
	direct := make(map[domain.ComponentID][]ConfigurationResource)
	seen := make(map[string]bool)
	for _, resource := range resources {
		if _, exists := model.Catalog().Component(resource.ComponentID); !exists {
			return nil, fmt.Errorf("configuration resource %q has unknown component %q", resource.ID, resource.ComponentID)
		}
		if resource.ID == "" || seen[resource.ID] {
			return nil, fmt.Errorf("invalid duplicate configuration resource %q", resource.ID)
		}
		seen[resource.ID] = true
		observation := observations[resource.ID]
		direct[resource.ComponentID] = append(
			direct[resource.ComponentID],
			ConfigurationResource{
				ID: resource.ID, Strategy: resource.Strategy,
				Status: observation.Status, Reason: observation.Reason,
			},
		)
	}
	result := make(map[domain.ComponentID][]ConfigurationResource)
	for visible, components := range dependencies {
		for _, component := range components {
			result[visible] = append(result[visible], direct[component]...)
		}
		sort.Slice(result[visible], func(i, j int) bool {
			return result[visible][i].ID < result[visible][j].ID
		})
	}
	return result, nil
}

func visibleDependencyClosures(model installmodel.Model) (map[domain.ComponentID][]domain.ComponentID, error) {
	result := make(map[domain.ComponentID][]domain.ComponentID, len(visibleTargets))
	for _, id := range visibleTargets {
		closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{id})
		if err != nil {
			return nil, fmt.Errorf("resolve dependencies for %q: %w", id, err)
		}
		result[id] = closure
	}
	return result, nil
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
		if !exists || len(component.Artifacts) != expected {
			return StatusAttention
		}
		for _, artifact := range component.Artifacts {
			if artifact.Ownership != domain.OwnershipManagedExact {
				return StatusAttention
			}
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
