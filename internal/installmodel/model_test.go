package installmodel_test

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestModelOwnsCatalogAndDeterministicArtifacts(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: "z", Dependencies: []domain.ComponentID{"a"}, Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "z/file"), SourcePath: "dist/z/file"}}},
		{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootCodexConfig, "same"), SourcePath: "dist/a/file", LegacyTargetSuffixes: []domain.ArtifactPath{"old/a/file"}}}, LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "a/legacy"), TargetSuffixes: []domain.ArtifactPath{"old/a/legacy"}}}},
	})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{"z"})
	if err != nil || !reflect.DeepEqual(closure, []domain.ComponentID{"a", "z"}) {
		t.Fatalf("closure = %v, error = %v", closure, err)
	}
	component, exists := model.Catalog().Component("a")
	if !exists || len(component.Artifacts) != 1 || component.Artifacts[0].Target != loc(domain.RootCodexConfig, "same") {
		t.Fatalf("catalog component = %#v, exists = %v", component, exists)
	}
	want := []installmodel.Artifact{
		{ComponentID: "a", Target: loc(domain.RootCodexConfig, "same"), SourcePath: "dist/a/file", LegacyTargetSuffixes: []domain.ArtifactPath{"old/a/file"}},
		{ComponentID: "a", Target: loc(domain.RootHome, "a/legacy"), LegacyTargetSuffixes: []domain.ArtifactPath{"old/a/legacy"}, LegacyOnly: true},
		{ComponentID: "z", Target: loc(domain.RootHome, "z/file"), SourcePath: "dist/z/file"},
	}
	if got := model.Artifacts(); !reflect.DeepEqual(got, want) {
		t.Fatalf("artifacts = %#v, want %#v", got, want)
	}
}

func TestModelDeepCopiesDesiredAndLegacyInputOutput(t *testing.T) {
	input := []installmodel.ComponentSpec{{
		ID: "component", Dependencies: []domain.ComponentID{"dependency"},
		Artifacts:       []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "desired"), SourcePath: "source/desired", LegacyTargetSuffixes: []domain.ArtifactPath{"old/desired"}}},
		LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "legacy"), TargetSuffixes: []domain.ArtifactPath{"old/legacy"}}},
	}, {ID: "dependency"}}
	model, err := installmodel.New(input)
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	input[0].Dependencies[0] = "changed"
	input[0].Artifacts[0].Target.Path = "changed"
	input[0].Artifacts[0].LegacyTargetSuffixes[0] = "changed"
	input[0].LegacyArtifacts[0].TargetSuffixes[0] = "changed"
	first := model.Artifacts()
	first[0].Target.Path = "returned-change"
	first[0].LegacyTargetSuffixes[0] = "returned-change"

	got := model.Artifacts()
	if got[0].Target.Path != "desired" || got[0].LegacyTargetSuffixes[0] != "old/desired" || got[1].LegacyTargetSuffixes[0] != "old/legacy" {
		t.Fatalf("model changed through external slices: %#v", got)
	}
	closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{"component"})
	if err != nil || !reflect.DeepEqual(closure, []domain.ComponentID{"component", "dependency"}) {
		t.Fatalf("closure = %v, error = %v", closure, err)
	}
}

func TestModelAllowsSamePathUnderDifferentRoots(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{{ID: "component", Artifacts: []installmodel.ArtifactSpec{
		{Target: loc(domain.RootClaudeConfig, "same"), SourcePath: "source/a"},
		{Target: loc(domain.RootCodexConfig, "same"), SourcePath: "source/b"},
	}}})
	if err != nil || len(model.Artifacts()) != 2 {
		t.Fatalf("artifacts = %#v, error = %v", model.Artifacts(), err)
	}
}

func TestModelRejectsInvalidDefinitions(t *testing.T) {
	tests := []struct {
		name       string
		components []installmodel.ComponentSpec
		message    string
	}{
		{name: "empty component", components: []installmodel.ComponentSpec{{}}, message: "component ID"},
		{name: "duplicate component", components: []installmodel.ComponentSpec{{ID: "a"}, {ID: "a"}}, message: "duplicate component"},
		{name: "invalid desired target", components: desiredComponent(domain.Location{Root: "Invalid", Path: "file"}, "source/file"), message: "target"},
		{name: "non-portable desired target", components: desiredComponent(loc(domain.RootHome, "é/file"), "source/file"), message: "target"},
		{name: "invalid source", components: desiredComponent(loc(domain.RootHome, "file"), "../source"), message: "source path"},
		{name: "non-portable source", components: desiredComponent(loc(domain.RootHome, "file"), "source/é"), message: "source path"},
		{name: "invalid desired suffix", components: []installmodel.ComponentSpec{{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "file"), SourcePath: "source/file", LegacyTargetSuffixes: []domain.ArtifactPath{"../legacy"}}}}}, message: "legacy target suffix"},
		{name: "non-portable desired suffix", components: []installmodel.ComponentSpec{{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "file"), SourcePath: "source/file", LegacyTargetSuffixes: []domain.ArtifactPath{"legacy/é"}}}}}, message: "legacy target suffix"},
		{name: "legacy without suffix", components: []installmodel.ComponentSpec{{ID: "a", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "legacy")}}}}, message: "at least one"},
		{name: "invalid legacy target", components: []installmodel.ComponentSpec{{ID: "a", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: domain.Location{Root: domain.RootHome}, TargetSuffixes: []domain.ArtifactPath{"legacy"}}}}}, message: "target"},
		{name: "invalid legacy suffix", components: []installmodel.ComponentSpec{{ID: "a", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "legacy"), TargetSuffixes: []domain.ArtifactPath{"../legacy"}}}}}, message: "target suffix"},
		{name: "non-portable legacy suffix", components: []installmodel.ComponentSpec{{ID: "a", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "legacy"), TargetSuffixes: []domain.ArtifactPath{"legacy/é"}}}}}, message: "target suffix"},
		{name: "unknown dependency", components: []installmodel.ComponentSpec{{ID: "a", Dependencies: []domain.ComponentID{"missing"}}}, message: "unknown component"},
		{name: "cycle", components: []installmodel.ComponentSpec{{ID: "a", Dependencies: []domain.ComponentID{"b"}}, {ID: "b", Dependencies: []domain.ComponentID{"a"}}}, message: "dependency cycle"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := installmodel.New(tt.components)
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestModelRejectsTargetOverlapWithinLogicalRoot(t *testing.T) {
	tests := []struct {
		name       string
		components []installmodel.ComponentSpec
	}{
		{name: "exact", components: []installmodel.ComponentSpec{{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "same"), SourcePath: "source/a"}}}, {ID: "b", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "same"), TargetSuffixes: []domain.ArtifactPath{"legacy"}}}}}},
		{name: "ancestor", components: []installmodel.ComponentSpec{{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootHome, "tree"), SourcePath: "source/a"}}}, {ID: "b", LegacyArtifacts: []installmodel.LegacyArtifactSpec{{Target: loc(domain.RootHome, "tree/child"), TargetSuffixes: []domain.ArtifactPath{"legacy"}}}}}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := installmodel.New(tt.components)
			if err == nil || !strings.Contains(err.Error(), "overlap") {
				t.Fatalf("expected overlap error, got %v", err)
			}
		})
	}
}

func desiredComponent(target domain.Location, source domain.ArtifactPath) []installmodel.ComponentSpec {
	return []installmodel.ComponentSpec{{ID: "component", Artifacts: []installmodel.ArtifactSpec{{Target: target, SourcePath: source}}}}
}

func loc(root domain.RootID, artifactPath domain.ArtifactPath) domain.Location {
	return domain.Location{Root: root, Path: artifactPath}
}
