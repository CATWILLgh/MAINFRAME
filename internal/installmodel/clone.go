package installmodel

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

func cloneComponents(components []ComponentSpec) []ComponentSpec {
	cloned := make([]ComponentSpec, len(components))
	for i, component := range components {
		cloned[i] = component
		cloned[i].Dependencies = append([]domain.ComponentID(nil), component.Dependencies...)
		cloned[i].Artifacts = make([]ArtifactSpec, len(component.Artifacts))
		for j, artifact := range component.Artifacts {
			cloned[i].Artifacts[j] = artifact
			cloned[i].Artifacts[j].LegacyTargetSuffixes = append(
				[]domain.ArtifactPath(nil),
				artifact.LegacyTargetSuffixes...,
			)
		}
	}
	return cloned
}

func cloneArtifacts(artifacts []Artifact) []Artifact {
	cloned := make([]Artifact, len(artifacts))
	for i, artifact := range artifacts {
		cloned[i] = artifact
		cloned[i].LegacyTargetSuffixes = append(
			[]domain.ArtifactPath(nil),
			artifact.LegacyTargetSuffixes...,
		)
	}
	return cloned
}
