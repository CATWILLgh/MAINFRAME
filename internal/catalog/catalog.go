package catalog

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Component struct {
	ID           domain.ComponentID
	Dependencies []domain.ComponentID
	Artifacts    []Artifact
}

type Artifact struct {
	Target     domain.Location
	SourcePath domain.ArtifactPath
}

type Catalog struct {
	components map[domain.ComponentID]Component
}

func New(components []Component) (Catalog, error) {
	registry := Catalog{components: make(map[domain.ComponentID]Component, len(components))}
	artifactOwners := make(map[domain.Location]domain.ComponentID)
	for _, component := range components {
		if component.ID == "" {
			return Catalog{}, fmt.Errorf("component ID must not be empty")
		}
		if _, exists := registry.components[component.ID]; exists {
			return Catalog{}, fmt.Errorf("duplicate component %q", component.ID)
		}
		for _, artifact := range component.Artifacts {
			if !artifact.Target.Valid() || !artifact.Target.Path.Portable() {
				return Catalog{}, fmt.Errorf("invalid artifact target %#v for component %q", artifact.Target, component.ID)
			}
			if !artifact.SourcePath.Portable() {
				return Catalog{}, fmt.Errorf("invalid source path %q for component %q", artifact.SourcePath, component.ID)
			}
			if owner, exists := artifactOwners[artifact.Target]; exists {
				return Catalog{}, fmt.Errorf(
					"duplicate artifact target %#v claimed by %q and %q",
					artifact.Target,
					owner,
					component.ID,
				)
			}
			artifactOwners[artifact.Target] = component.ID
		}
		registry.components[component.ID] = cloneComponent(component)
	}
	if err := registry.validateDependencies(); err != nil {
		return Catalog{}, err
	}
	return registry, nil
}

func (catalog Catalog) Knows(id domain.ComponentID) bool {
	_, exists := catalog.components[id]
	return exists
}

func (catalog Catalog) Component(id domain.ComponentID) (Component, bool) {
	component, exists := catalog.components[id]
	return cloneComponent(component), exists
}

func (catalog Catalog) DependencyClosure(requested []domain.ComponentID) ([]domain.ComponentID, error) {
	visited := make(map[domain.ComponentID]bool, len(requested))
	var visit func(domain.ComponentID) error
	visit = func(id domain.ComponentID) error {
		component, exists := catalog.components[id]
		if !exists {
			return fmt.Errorf("unknown component %q", id)
		}
		if visited[id] {
			return nil
		}
		visited[id] = true
		for _, dependency := range component.Dependencies {
			if err := visit(dependency); err != nil {
				return err
			}
		}
		return nil
	}
	for _, id := range requested {
		if err := visit(id); err != nil {
			return nil, err
		}
	}
	return sortedIDs(visited), nil
}

func (catalog Catalog) validateDependencies() error {
	for id, component := range catalog.components {
		for _, dependency := range component.Dependencies {
			if !catalog.Knows(dependency) {
				return fmt.Errorf("component %q depends on unknown component %q", id, dependency)
			}
		}
	}
	return catalog.validateCycles()
}

func (catalog Catalog) validateCycles() error {
	const (
		visiting = 1
		visited  = 2
	)
	states := make(map[domain.ComponentID]int, len(catalog.components))
	var visit func(domain.ComponentID) error
	visit = func(id domain.ComponentID) error {
		if states[id] == visiting {
			return fmt.Errorf("dependency cycle includes component %q", id)
		}
		if states[id] == visited {
			return nil
		}
		states[id] = visiting
		for _, dependency := range catalog.components[id].Dependencies {
			if err := visit(dependency); err != nil {
				return err
			}
		}
		states[id] = visited
		return nil
	}
	for id := range catalog.components {
		if err := visit(id); err != nil {
			return err
		}
	}
	return nil
}

func sortedIDs(set map[domain.ComponentID]bool) []domain.ComponentID {
	ids := make([]domain.ComponentID, 0, len(set))
	for id := range set {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	return ids
}

func cloneComponent(component Component) Component {
	component.Dependencies = append([]domain.ComponentID(nil), component.Dependencies...)
	component.Artifacts = append([]Artifact(nil), component.Artifacts...)
	return component
}
