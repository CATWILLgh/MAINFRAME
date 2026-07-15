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
	if err := validateObserved(request.Observed); err != nil {
		return domain.Plan{}, err
	}
	desired, err := planner.catalog.DependencyClosure(request.Desired.Components)
	if err != nil {
		return domain.Plan{}, err
	}
	expectedOwners := planner.expectedOwners(desired)
	observedByPath := indexObservedArtifacts(request.Observed)
	operations := planner.operationsForDesired(desired, observedByPath)
	operations = append(operations, planner.operationsForObserved(request.Observed, expectedOwners)...)
	sortOperations(operations)
	return domain.Plan{Operations: operations}, nil
}

func (planner Planner) operationsForDesired(
	desired []domain.ComponentID,
	observedByPath map[domain.ArtifactPath]observedArtifact,
) []domain.Operation {
	operations := make([]domain.Operation, 0)
	for _, id := range desired {
		component, _ := planner.catalog.Component(id)
		for _, expected := range component.Artifacts {
			observed, exists := observedByPath[expected.Path]
			if exists && observed.componentID == id && observed.artifact.Ownership == domain.OwnershipManagedExact {
				continue
			}
			kind := domain.OperationInstall
			artifact := domain.Artifact{Path: expected.Path}
			if exists {
				kind = domain.OperationConflict
				artifact = observed.artifact
			}
			operations = append(operations, domain.Operation{
				ComponentID: id,
				Kind:        kind,
				Artifact:    artifact,
			})
		}
	}
	return operations
}

func (planner Planner) operationsForObserved(
	observed domain.ObservedState,
	expectedOwners map[domain.ArtifactPath]domain.ComponentID,
) []domain.Operation {
	operations := make([]domain.Operation, 0)
	for _, component := range observed.Components {
		for _, artifact := range component.Artifacts {
			if _, expected := expectedOwners[artifact.Path]; expected {
				continue
			}
			kind := domain.OperationConflict
			if planner.catalog.Knows(component.ID) && artifact.Ownership.Removable() {
				kind = domain.OperationRemove
			}
			operations = append(operations, domain.Operation{
				ComponentID: component.ID,
				Kind:        kind,
				Artifact:    artifact,
			})
		}
	}
	return operations
}

func (planner Planner) expectedOwners(desired []domain.ComponentID) map[domain.ArtifactPath]domain.ComponentID {
	owners := make(map[domain.ArtifactPath]domain.ComponentID)
	for _, id := range desired {
		component, _ := planner.catalog.Component(id)
		for _, artifact := range component.Artifacts {
			owners[artifact.Path] = id
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
		if left.Artifact.Path != right.Artifact.Path {
			return left.Artifact.Path < right.Artifact.Path
		}
		return left.Artifact.Ownership < right.Artifact.Ownership
	})
}

type observedArtifact struct {
	componentID domain.ComponentID
	artifact    domain.Artifact
}

func indexObservedArtifacts(observed domain.ObservedState) map[domain.ArtifactPath]observedArtifact {
	artifacts := make(map[domain.ArtifactPath]observedArtifact)
	for _, component := range observed.Components {
		for _, artifact := range component.Artifacts {
			artifacts[artifact.Path] = observedArtifact{componentID: component.ID, artifact: artifact}
		}
	}
	return artifacts
}

func validateObserved(observed domain.ObservedState) error {
	components := make(map[domain.ComponentID]bool, len(observed.Components))
	paths := make(map[domain.ArtifactPath]bool)
	for _, component := range observed.Components {
		if component.ID == "" {
			return fmt.Errorf("observed component ID must not be empty")
		}
		if components[component.ID] {
			return fmt.Errorf("duplicate observed component %q", component.ID)
		}
		components[component.ID] = true
		for _, artifact := range component.Artifacts {
			if artifact.Path == "" {
				return fmt.Errorf("observed artifact path must not be empty for component %q", component.ID)
			}
			if !artifact.Path.Valid() {
				return fmt.Errorf("invalid artifact path %q for observed component %q", artifact.Path, component.ID)
			}
			if paths[artifact.Path] {
				return fmt.Errorf("duplicate observed artifact path %q", artifact.Path)
			}
			paths[artifact.Path] = true
			if !artifact.Ownership.Valid() {
				return fmt.Errorf("invalid ownership %q for artifact %q", artifact.Ownership, artifact.Path)
			}
		}
	}
	return nil
}
