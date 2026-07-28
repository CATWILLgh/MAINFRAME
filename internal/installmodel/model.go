package installmodel

import (
	"fmt"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type ArtifactSpec struct {
	UnitID               string
	Target               domain.Location
	SourcePath           domain.ArtifactPath
	LegacyTargetSuffixes []domain.ArtifactPath
	Feature              domain.FeatureID
}

type LegacyArtifactSpec struct {
	Target         domain.Location
	TargetSuffixes []domain.ArtifactPath
}

type ComponentSpec struct {
	ID              domain.ComponentID
	Dependencies    []domain.ComponentID
	Artifacts       []ArtifactSpec
	LegacyArtifacts []LegacyArtifactSpec
}

type Artifact struct {
	UnitID               string
	ComponentID          domain.ComponentID
	Target               domain.Location
	SourcePath           domain.ArtifactPath
	LegacyTargetSuffixes []domain.ArtifactPath
	LegacyOnly           bool
	Feature              domain.FeatureID
}

type Model struct {
	catalog   catalog.Catalog
	artifacts []Artifact
}

func New(components []ComponentSpec) (Model, error) {
	copied := cloneComponents(components)
	artifacts, err := validateAndFlatten(copied)
	if err != nil {
		return Model{}, err
	}
	componentCatalog, err := deriveCatalog(copied)
	if err != nil {
		return Model{}, err
	}
	sortArtifacts(artifacts)
	return Model{catalog: componentCatalog, artifacts: artifacts}, nil
}

func (model Model) Catalog() catalog.Catalog {
	return model.catalog
}

func (model Model) Artifacts() []Artifact {
	return cloneArtifacts(model.artifacts)
}

func validateAndFlatten(components []ComponentSpec) ([]Artifact, error) {
	var artifacts []Artifact
	for _, component := range components {
		for _, spec := range component.Artifacts {
			if err := validateDesired(component.ID, spec); err != nil {
				return nil, err
			}
			artifacts = append(artifacts, desiredArtifact(component.ID, spec))
		}
		for _, spec := range component.LegacyArtifacts {
			if err := validateLegacy(component.ID, spec); err != nil {
				return nil, err
			}
			artifacts = append(artifacts, legacyArtifact(component.ID, spec))
		}
	}
	if err := validateTargetOverlap(artifacts); err != nil {
		return nil, err
	}
	return artifacts, nil
}

func validateDesired(id domain.ComponentID, spec ArtifactSpec) error {
	if spec.UnitID != "" && !domain.ValidUnitID(spec.UnitID) {
		return fmt.Errorf("component %q has invalid unit ID %q", id, spec.UnitID)
	}
	if !spec.Target.Valid() || !spec.Target.Path.Portable() {
		return fmt.Errorf("component %q has invalid artifact target %#v", id, spec.Target)
	}
	if !spec.SourcePath.Portable() {
		return fmt.Errorf("component %q has invalid source path %q", id, spec.SourcePath)
	}
	if spec.Feature != "" && !spec.Feature.Valid() {
		return fmt.Errorf("component %q has invalid feature %q", id, spec.Feature)
	}
	for _, suffix := range spec.LegacyTargetSuffixes {
		if !suffix.Portable() {
			return fmt.Errorf("component %q has invalid legacy target suffix %q", id, suffix)
		}
	}
	return nil
}

func validateLegacy(id domain.ComponentID, spec LegacyArtifactSpec) error {
	if !spec.Target.Valid() || !spec.Target.Path.Portable() {
		return fmt.Errorf("component %q has invalid legacy target %#v", id, spec.Target)
	}
	if len(spec.TargetSuffixes) == 0 {
		return fmt.Errorf("component %q legacy artifact requires at least one target suffix", id)
	}
	for _, suffix := range spec.TargetSuffixes {
		if !suffix.Portable() {
			return fmt.Errorf("component %q has invalid legacy target suffix %q", id, suffix)
		}
	}
	return nil
}

func validateTargetOverlap(artifacts []Artifact) error {
	for i := range artifacts {
		for j := 0; j < i; j++ {
			left, right := artifacts[i].Target, artifacts[j].Target
			if left.Root == right.Root && pathsOverlap(left.Path, right.Path) {
				return fmt.Errorf("artifact targets %#v and %#v overlap", left, right)
			}
		}
	}
	return nil
}

func pathsOverlap(left, right domain.ArtifactPath) bool {
	leftPath, rightPath := string(left), string(right)
	return leftPath == rightPath || strings.HasPrefix(leftPath, rightPath+"/") || strings.HasPrefix(rightPath, leftPath+"/")
}

func deriveCatalog(components []ComponentSpec) (catalog.Catalog, error) {
	definitions := make([]catalog.Component, 0, len(components))
	for _, component := range components {
		artifacts := make([]catalog.Artifact, 0, len(component.Artifacts))
		for _, spec := range component.Artifacts {
			artifacts = append(artifacts, catalog.Artifact{
				UnitID: spec.UnitID, Target: spec.Target,
				SourcePath: spec.SourcePath, Feature: spec.Feature,
			})
		}
		definitions = append(definitions, catalog.Component{ID: component.ID, Dependencies: component.Dependencies, Artifacts: artifacts})
	}
	return catalog.New(definitions)
}

func desiredArtifact(id domain.ComponentID, spec ArtifactSpec) Artifact {
	return Artifact{UnitID: spec.UnitID, ComponentID: id, Target: spec.Target, SourcePath: spec.SourcePath, LegacyTargetSuffixes: append([]domain.ArtifactPath(nil), spec.LegacyTargetSuffixes...), Feature: spec.Feature}
}

func legacyArtifact(id domain.ComponentID, spec LegacyArtifactSpec) Artifact {
	return Artifact{ComponentID: id, Target: spec.Target, LegacyTargetSuffixes: append([]domain.ArtifactPath(nil), spec.TargetSuffixes...), LegacyOnly: true}
}

func sortArtifacts(artifacts []Artifact) {
	sort.Slice(artifacts, func(i, j int) bool {
		left, right := artifacts[i], artifacts[j]
		if left.Target.Root != right.Target.Root {
			return left.Target.Root < right.Target.Root
		}
		if left.Target.Path != right.Target.Path {
			return left.Target.Path < right.Target.Path
		}
		if left.ComponentID != right.ComponentID {
			return left.ComponentID < right.ComponentID
		}
		return !left.LegacyOnly && right.LegacyOnly
	})
}
