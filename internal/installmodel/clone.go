package installmodel

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

func cloneComponents(components []ComponentSpec) []ComponentSpec {
	cloned := make([]ComponentSpec, len(components))
	for i, component := range components {
		cloned[i] = component
		cloned[i].Dependencies = append([]domain.ComponentID(nil), component.Dependencies...)
		cloned[i].Artifacts = cloneDesiredSpecs(component.Artifacts)
		cloned[i].LegacyArtifacts = cloneLegacySpecs(component.LegacyArtifacts)
	}
	return cloned
}

func cloneDesiredSpecs(specs []ArtifactSpec) []ArtifactSpec {
	cloned := make([]ArtifactSpec, len(specs))
	for i, spec := range specs {
		cloned[i] = spec
		cloned[i].LegacyTargetSuffixes = append([]domain.ArtifactPath(nil), spec.LegacyTargetSuffixes...)
	}
	return cloned
}

func cloneLegacySpecs(specs []LegacyArtifactSpec) []LegacyArtifactSpec {
	cloned := make([]LegacyArtifactSpec, len(specs))
	for i, spec := range specs {
		cloned[i] = spec
		cloned[i].TargetSuffixes = append([]domain.ArtifactPath(nil), spec.TargetSuffixes...)
	}
	return cloned
}

func cloneArtifacts(artifacts []Artifact) []Artifact {
	cloned := make([]Artifact, len(artifacts))
	for i, artifact := range artifacts {
		cloned[i] = artifact
		cloned[i].LegacyTargetSuffixes = append([]domain.ArtifactPath(nil), artifact.LegacyTargetSuffixes...)
	}
	return cloned
}
