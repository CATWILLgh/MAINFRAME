package lifecycle

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
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
	domain.ComponentZCodeDesktop,
	domain.ComponentAntigravity2,
}

type Target struct {
	ID                domain.ComponentID
	Status            TargetStatus
	Selected          bool
	Configuration     []ConfigurationResource
	HostCompatibility *hostcompatibility.Assessment
}

type ConfigurationStatus = configuration.Status
type ConfigurationReason = configuration.Reason

const (
	ConfigurationReady         = configuration.Ready
	ConfigurationNeedsChange   = configuration.NeedsChange
	ConfigurationNotApplicable = configuration.NotApplicable
	ConfigurationAttention     = configuration.Attention
	ConfigurationNotAssessed   = configuration.NotAssessed

	ConfigurationResourceExists           = configuration.ResourceExists
	ConfigurationDirectoryExists          = configuration.DirectoryExists
	ConfigurationLinePresent              = configuration.LinePresent
	ConfigurationResourceMissing          = configuration.ResourceMissing
	ConfigurationDirectoryMissing         = configuration.DirectoryMissing
	ConfigurationLineMissing              = configuration.LineMissing
	ConfigurationOptionalTargetMissing    = configuration.OptionalTargetMissing
	ConfigurationSymbolicLink             = configuration.SymbolicLink
	ConfigurationWrongKind                = configuration.WrongKind
	ConfigurationInspectionFailed         = configuration.InspectionFailed
	ConfigurationObservationUnsupported   = configuration.ObservationUnsupported
	ConfigurationJSONFieldsMatch          = configuration.JSONFieldsMatch
	ConfigurationJSONFieldsDrifted        = configuration.JSONFieldsDrifted
	ConfigurationJSONDocumentInvalid      = configuration.JSONDocumentInvalid
	ConfigurationExternalStateSatisfied   = configuration.ExternalStateSatisfied
	ConfigurationManualActionRequired     = configuration.ManualActionRequired
	ConfigurationExternalStateUnavailable = configuration.ExternalStateUnavailable
	ConfigurationExternalInspectionFailed = configuration.ExternalInspectionFailed
)

type ConfigurationResource struct {
	ID       string
	Strategy releasecontract.ResourceStrategy
	Status   ConfigurationStatus
	Reason   ConfigurationReason
}

type Preview struct {
	Filesystem    domain.Plan
	Configuration configuration.Plan
	MCP           mcpconfiguration.Plan
	Diagnostics   diagnostics.Plan
}

type PreviewRequest struct {
	Components     []domain.ComponentID
	MCPSelections  []mcpcatalog.Selection
	MCPCredentials []mcpconfiguration.CredentialBinding
	Diagnostics    diagnostics.Desired
}

type Service struct {
	planner                 plan.Planner
	observed                domain.ObservedState
	desiredCounts           map[domain.ComponentID]int
	featureTargets          map[domain.ComponentID]map[domain.Location]bool
	dependencies            map[domain.ComponentID][]domain.ComponentID
	configuration           map[domain.ComponentID][]ConfigurationResource
	configurationInspection *configuration.Inspection
	configurationFallback   configuration.Plan
	mcpInspection           *mcpconfiguration.Inspection
	hostCompatibility       map[domain.ComponentID]hostcompatibility.Assessment
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
	service, err := newService(model, observed, resources, indexed)
	if err != nil {
		return Service{}, err
	}
	service.configurationFallback = unavailableConfigurationPlan(resources, indexed)
	return service, nil
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
		planner:        planner,
		observed:       cloneObserved(observed),
		desiredCounts:  countDesiredArtifacts(model),
		featureTargets: featureArtifactTargets(model),
		dependencies:   dependencies,
		configuration:  configurationInventory,
	}, nil
}

func (service Service) Targets() []Target {
	observed := make(map[domain.ComponentID]domain.ObservedComponent)
	for _, component := range service.observed.Components {
		observed[component.ID] = component
	}
	targets := make([]Target, 0, len(visibleTargets))
	for _, id := range visibleTargets {
		if _, available := service.dependencies[id]; !available {
			continue
		}
		compatibility := service.hostCompatibilityFor(id)
		targets = append(targets, Target{
			ID:                id,
			Status:            service.status(id, observed),
			Selected:          observed[id].ID != "" && hostSelectable(compatibility),
			Configuration:     append([]ConfigurationResource(nil), service.configuration[id]...),
			HostCompatibility: compatibility,
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
		if !model.Catalog().Knows(id) {
			continue
		}
		closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{id})
		if err != nil {
			return nil, fmt.Errorf("resolve dependencies for %q: %w", id, err)
		}
		result[id] = closure
	}
	return result, nil
}

func (service Service) Plan(components []domain.ComponentID) (domain.Plan, error) {
	return service.planFilesystem(components, nil)
}

func (service Service) planFilesystem(
	components []domain.ComponentID,
	features []domain.FeatureID,
) (domain.Plan, error) {
	seen := make(map[domain.ComponentID]bool, len(components))
	for _, id := range components {
		if !selectable(id) {
			return domain.Plan{}, fmt.Errorf("component %q is not selectable", id)
		}
		if !hostSelectable(service.hostCompatibilityFor(id)) {
			return domain.Plan{}, fmt.Errorf("component %q does not satisfy its host requirement", id)
		}
		if seen[id] {
			return domain.Plan{}, fmt.Errorf("duplicate selected component %q", id)
		}
		seen[id] = true
	}
	return service.planner.PlanWithPreservation(domain.PlanRequest{
		Desired: domain.DesiredState{
			Components: append([]domain.ComponentID(nil), components...),
			Features:   append([]domain.FeatureID(nil), features...),
		},
		Observed: cloneObserved(service.observed),
	}, service.preservationRoots(components))
}

func (service Service) WithHostCompatibility(
	assessments []hostcompatibility.Assessment,
) (Service, error) {
	indexed := make(map[domain.ComponentID]hostcompatibility.Assessment, len(assessments))
	for _, assessment := range assessments {
		if assessment.ComponentID == "" || !validHostStatus(assessment.Status) {
			return Service{}, fmt.Errorf("invalid host compatibility assessment for %q", assessment.ComponentID)
		}
		if _, duplicate := indexed[assessment.ComponentID]; duplicate {
			return Service{}, fmt.Errorf("duplicate host compatibility assessment for %q", assessment.ComponentID)
		}
		assessment.DetectedVersions = append([]string(nil), assessment.DetectedVersions...)
		assessment.ExpectedVersions = append([]string(nil), assessment.ExpectedVersions...)
		indexed[assessment.ComponentID] = assessment
	}
	service.hostCompatibility = indexed
	return service, nil
}

func (service Service) preservationRoots(selected []domain.ComponentID) []domain.ComponentID {
	selectedSet := make(map[domain.ComponentID]bool, len(selected))
	for _, component := range selected {
		selectedSet[component] = true
	}
	observedSet := make(map[domain.ComponentID]bool, len(service.observed.Components))
	for _, component := range service.observed.Components {
		observedSet[component.ID] = true
	}
	var result []domain.ComponentID
	for _, target := range visibleTargets {
		if _, available := service.dependencies[target]; !available {
			continue
		}
		if !selectedSet[target] && observedSet[target] &&
			!hostSelectable(service.hostCompatibilityFor(target)) {
			result = append(result, target)
		}
	}
	return result
}

func (service Service) hostCompatibilityFor(id domain.ComponentID) *hostcompatibility.Assessment {
	assessment, exists := service.hostCompatibility[id]
	if !exists {
		return nil
	}
	assessment.DetectedVersions = append([]string(nil), assessment.DetectedVersions...)
	assessment.ExpectedVersions = append([]string(nil), assessment.ExpectedVersions...)
	return &assessment
}

func hostSelectable(assessment *hostcompatibility.Assessment) bool {
	return assessment == nil || assessment.Status == hostcompatibility.StatusSatisfied
}

func validHostStatus(status hostcompatibility.Status) bool {
	switch status {
	case hostcompatibility.StatusSatisfied, hostcompatibility.StatusMissing,
		hostcompatibility.StatusIncompatible, hostcompatibility.StatusUnavailable:
		return true
	default:
		return false
	}
}

func selectable(id domain.ComponentID) bool {
	for _, candidate := range visibleTargets {
		if id == candidate {
			return true
		}
	}
	return false
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
