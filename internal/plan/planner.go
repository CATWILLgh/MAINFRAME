package plan

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Planner struct {
	catalog catalog.Catalog
}

func New(componentCatalog catalog.Catalog) Planner {
	return Planner{catalog: componentCatalog}
}

func (planner Planner) Plan(request domain.PlanRequest) (domain.Plan, error) {
	return planner.PlanWithPreservation(request, nil)
}

func (planner Planner) PlanWithPreservation(
	request domain.PlanRequest,
	preserveRoots []domain.ComponentID,
) (domain.Plan, error) {
	if err := validateObserved(request.Observed); err != nil {
		return domain.Plan{}, err
	}
	desired, err := planner.catalog.DependencyClosure(request.Desired.Components)
	if err != nil {
		return domain.Plan{}, err
	}
	preserved, err := planner.catalog.DependencyClosure(preserveRoots)
	if err != nil {
		return domain.Plan{}, err
	}
	preserveOnly := componentDifference(preserved, desired)
	expectedOwners := planner.expectedOwners(desired)
	observedByLocation := indexObservedArtifacts(request.Observed)
	operations := planner.operationsForDesired(desired, observedByLocation)
	operations = append(
		operations,
		planner.operationsForObserved(request.Observed, expectedOwners, preserveOnly)...,
	)
	sortOperations(operations)
	return domain.Plan{Operations: operations}, nil
}

func (planner Planner) operationsForDesired(
	desired []domain.ComponentID,
	observedByLocation map[domain.Location]observedArtifact,
) []domain.Operation {
	operations := make([]domain.Operation, 0)
	for _, id := range desired {
		component, _ := planner.catalog.Component(id)
		for _, expected := range component.Artifacts {
			observed, exists := observedByLocation[expected.Target]
			if exists && observed.componentID == id &&
				observed.artifact.Ownership == domain.OwnershipManagedExact &&
				(expected.UnitID == "" || observed.artifact.UnitID == expected.UnitID) {
				continue
			}
			kind := domain.OperationInstall
			artifact := domain.Artifact{Location: expected.Target}
			sourcePath := expected.SourcePath
			if exists {
				artifact = observed.artifact
				if observed.componentID == id && expected.UnitID != "" &&
					observed.artifact.UnitID == expected.UnitID {
					switch observed.artifact.Ownership {
					case domain.OwnershipManagedPrevious:
						kind = domain.OperationReplace
					case domain.OwnershipManagedMissing:
						kind = domain.OperationInstall
					case domain.OwnershipExactAdoptable:
						kind = domain.OperationAdopt
						sourcePath = ""
					default:
						kind = domain.OperationConflict
						sourcePath = ""
					}
				} else {
					kind = domain.OperationConflict
					sourcePath = ""
				}
			}
			operations = append(operations, domain.Operation{
				ComponentID: id,
				UnitID:      expected.UnitID,
				Kind:        kind,
				Artifact:    artifact,
				SourcePath:  sourcePath,
			})
		}
	}
	return operations
}

func (planner Planner) operationsForObserved(
	observed domain.ObservedState,
	expectedOwners map[domain.Location]domain.ComponentID,
	preserveOnly map[domain.ComponentID]bool,
) []domain.Operation {
	operations := make([]domain.Operation, 0)
	for _, component := range observed.Components {
		if preserveOnly[component.ID] {
			continue
		}
		for _, artifact := range component.Artifacts {
			if _, expected := expectedOwners[artifact.Location]; expected {
				continue
			}
			kind := domain.OperationConflict
			declaredArtifact, declared := planner.declaredArtifact(component.ID, artifact.Location)
			var sourcePath domain.ArtifactPath
			var unitID string
			if artifact.UnitID != "" && artifact.Ownership.Removable() {
				kind = domain.OperationRemove
				unitID = artifact.UnitID
			} else if artifact.UnitID != "" &&
				(artifact.Ownership == domain.OwnershipManagedDrifted ||
					artifact.Ownership == domain.OwnershipManagedMissing) {
				kind = domain.OperationRelinquish
				unitID = artifact.UnitID
			} else if declared && artifact.Ownership.Removable() {
				kind = domain.OperationRemove
				unitID = declaredArtifact.UnitID
				sourcePath = declaredArtifact.SourcePath
			}
			operations = append(operations, domain.Operation{
				ComponentID: component.ID,
				UnitID:      unitID,
				Kind:        kind,
				Artifact:    artifact,
				SourcePath:  sourcePath,
			})
		}
	}
	return operations
}

func componentDifference(
	components []domain.ComponentID,
	excluded []domain.ComponentID,
) map[domain.ComponentID]bool {
	excludedSet := make(map[domain.ComponentID]bool, len(excluded))
	for _, component := range excluded {
		excludedSet[component] = true
	}
	result := make(map[domain.ComponentID]bool, len(components))
	for _, component := range components {
		if !excludedSet[component] {
			result[component] = true
		}
	}
	return result
}

func (planner Planner) declaredArtifact(id domain.ComponentID, location domain.Location) (catalog.Artifact, bool) {
	component, exists := planner.catalog.Component(id)
	if !exists {
		return catalog.Artifact{}, false
	}
	for _, artifact := range component.Artifacts {
		if artifact.Target == location {
			return artifact, true
		}
	}
	return catalog.Artifact{}, false
}

func (planner Planner) expectedOwners(desired []domain.ComponentID) map[domain.Location]domain.ComponentID {
	owners := make(map[domain.Location]domain.ComponentID)
	for _, id := range desired {
		component, _ := planner.catalog.Component(id)
		for _, artifact := range component.Artifacts {
			owners[artifact.Target] = id
		}
	}
	return owners
}

func sortOperations(operations []domain.Operation) {
	sort.Slice(operations, func(i, j int) bool {
		left, right := operations[i], operations[j]
		if left.ComponentID != right.ComponentID {
			return left.ComponentID < right.ComponentID
		}
		if left.Kind != right.Kind {
			return left.Kind < right.Kind
		}
		if left.Artifact.Location.Root != right.Artifact.Location.Root {
			return left.Artifact.Location.Root < right.Artifact.Location.Root
		}
		if left.Artifact.Location.Path != right.Artifact.Location.Path {
			return left.Artifact.Location.Path < right.Artifact.Location.Path
		}
		if left.Artifact.Ownership != right.Artifact.Ownership {
			return left.Artifact.Ownership < right.Artifact.Ownership
		}
		return left.SourcePath < right.SourcePath
	})
}

type observedArtifact struct {
	componentID domain.ComponentID
	artifact    domain.Artifact
}

func indexObservedArtifacts(observed domain.ObservedState) map[domain.Location]observedArtifact {
	artifacts := make(map[domain.Location]observedArtifact)
	for _, component := range observed.Components {
		for _, artifact := range component.Artifacts {
			artifacts[artifact.Location] = observedArtifact{componentID: component.ID, artifact: artifact}
		}
	}
	return artifacts
}

func validateObserved(observed domain.ObservedState) error {
	components := make(map[domain.ComponentID]bool, len(observed.Components))
	locations := make(map[domain.Location]bool)
	for _, component := range observed.Components {
		if component.ID == "" {
			return fmt.Errorf("observed component ID must not be empty")
		}
		if components[component.ID] {
			return fmt.Errorf("duplicate observed component %q", component.ID)
		}
		components[component.ID] = true
		for _, artifact := range component.Artifacts {
			if !artifact.Location.Valid() {
				return fmt.Errorf("invalid artifact location %#v for observed component %q", artifact.Location, component.ID)
			}
			if locations[artifact.Location] {
				return fmt.Errorf("duplicate observed artifact location %#v", artifact.Location)
			}
			locations[artifact.Location] = true
			if !artifact.Ownership.Valid() {
				return fmt.Errorf("invalid ownership %q for artifact %#v", artifact.Ownership, artifact.Location)
			}
		}
	}
	return nil
}
