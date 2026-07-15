package installmodel

import (
	"fmt"
	"io/fs"
	"sort"
	"strings"
	"unicode"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type ArtifactSpec struct {
	HomePath             domain.ArtifactPath
	SourcePath           domain.ArtifactPath
	LegacyTargetSuffixes []domain.ArtifactPath
}

type ComponentSpec struct {
	ID           domain.ComponentID
	Dependencies []domain.ComponentID
	Artifacts    []ArtifactSpec
}

type Artifact struct {
	ComponentID          domain.ComponentID
	HomePath             domain.ArtifactPath
	SourcePath           domain.ArtifactPath
	LegacyTargetSuffixes []domain.ArtifactPath
}

type Model struct {
	catalog   catalog.Catalog
	artifacts []Artifact
}

func New(components []ComponentSpec) (Model, error) {
	copied := cloneComponents(components)
	if err := validateArtifactPaths(copied); err != nil {
		return Model{}, err
	}
	componentCatalog, err := deriveCatalog(copied)
	if err != nil {
		return Model{}, err
	}
	artifacts := flattenArtifacts(copied)
	sortArtifacts(artifacts)
	return Model{catalog: componentCatalog, artifacts: artifacts}, nil
}

func (model Model) Catalog() catalog.Catalog {
	return model.catalog
}

func (model Model) Artifacts() []Artifact {
	return cloneArtifacts(model.artifacts)
}

func validateArtifactPaths(components []ComponentSpec) error {
	homeOwners := make(map[domain.ArtifactPath]domain.ComponentID)
	homePaths := make([]ownedPath, 0)
	for _, component := range components {
		for _, artifact := range component.Artifacts {
			if !validModelPath(artifact.HomePath) {
				return fmt.Errorf("component %q has invalid home path %q", component.ID, artifact.HomePath)
			}
			if !validModelPath(artifact.SourcePath) {
				return fmt.Errorf("component %q has invalid source path %q", component.ID, artifact.SourcePath)
			}
			if owner, exists := homeOwners[artifact.HomePath]; exists {
				return fmt.Errorf("duplicate artifact path %q claimed by %q and %q", artifact.HomePath, owner, component.ID)
			}
			homeOwners[artifact.HomePath] = component.ID
			homePaths = append(homePaths, ownedPath{path: artifact.HomePath, owner: component.ID})
			for _, suffix := range artifact.LegacyTargetSuffixes {
				if !validModelPath(suffix) {
					return fmt.Errorf("component %q has invalid legacy target suffix %q", component.ID, suffix)
				}
			}
		}
	}
	return validateNoOverlappingHomePaths(homePaths)
}

func validModelPath(artifactPath domain.ArtifactPath) bool {
	if !artifactPath.Valid() || !fs.ValidPath(string(artifactPath)) {
		return false
	}
	for _, character := range artifactPath {
		if character > unicode.MaxASCII {
			return false
		}
	}
	return true
}

type ownedPath struct {
	path  domain.ArtifactPath
	owner domain.ComponentID
}

func validateNoOverlappingHomePaths(paths []ownedPath) error {
	sort.Slice(paths, func(i, j int) bool { return paths[i].path < paths[j].path })
	for parentIndex, parent := range paths {
		for _, child := range paths[parentIndex+1:] {
			if strings.HasPrefix(string(child.path), string(parent.path)+"/") {
				return fmt.Errorf(
					"overlapping artifact paths %q (%q) and %q (%q)",
					parent.path,
					parent.owner,
					child.path,
					child.owner,
				)
			}
		}
	}
	return nil
}

func deriveCatalog(components []ComponentSpec) (catalog.Catalog, error) {
	definitions := make([]catalog.Component, 0, len(components))
	for _, component := range components {
		artifacts := make([]domain.Artifact, 0, len(component.Artifacts))
		for _, artifact := range component.Artifacts {
			artifacts = append(artifacts, domain.Artifact{Path: artifact.HomePath})
		}
		definitions = append(definitions, catalog.Component{
			ID: component.ID, Dependencies: component.Dependencies, Artifacts: artifacts,
		})
	}
	return catalog.New(definitions)
}

func flattenArtifacts(components []ComponentSpec) []Artifact {
	var artifacts []Artifact
	for _, component := range components {
		for _, spec := range component.Artifacts {
			artifacts = append(artifacts, Artifact{
				ComponentID:          component.ID,
				HomePath:             spec.HomePath,
				SourcePath:           spec.SourcePath,
				LegacyTargetSuffixes: append([]domain.ArtifactPath(nil), spec.LegacyTargetSuffixes...),
			})
		}
	}
	return artifacts
}

func sortArtifacts(artifacts []Artifact) {
	sort.Slice(artifacts, func(i, j int) bool {
		if artifacts[i].ComponentID != artifacts[j].ComponentID {
			return artifacts[i].ComponentID < artifacts[j].ComponentID
		}
		if artifacts[i].HomePath != artifacts[j].HomePath {
			return artifacts[i].HomePath < artifacts[j].HomePath
		}
		return artifacts[i].SourcePath < artifacts[j].SourcePath
	})
}
