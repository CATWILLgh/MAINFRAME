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
		{ID: "z", Dependencies: []domain.ComponentID{"a"}, Artifacts: []installmodel.ArtifactSpec{{HomePath: "z/file", SourcePath: "dist/z/file"}}},
		{ID: "a", Artifacts: []installmodel.ArtifactSpec{{HomePath: "a/file", SourcePath: "dist/a/file", LegacyTargetSuffixes: []domain.ArtifactPath{"old/a/file"}}}},
	})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{"z"})
	if err != nil {
		t.Fatalf("dependency closure: %v", err)
	}
	if !reflect.DeepEqual(closure, []domain.ComponentID{"a", "z"}) {
		t.Fatalf("closure = %v", closure)
	}
	component, exists := model.Catalog().Component("a")
	if !exists || !reflect.DeepEqual(component.Artifacts, []domain.Artifact{{Path: "a/file"}}) {
		t.Fatalf("catalog component = %#v, exists = %v", component, exists)
	}
	want := []installmodel.Artifact{
		{ComponentID: "a", HomePath: "a/file", SourcePath: "dist/a/file", LegacyTargetSuffixes: []domain.ArtifactPath{"old/a/file"}},
		{ComponentID: "z", HomePath: "z/file", SourcePath: "dist/z/file"},
	}
	if got := model.Artifacts(); !reflect.DeepEqual(got, want) {
		t.Fatalf("artifacts = %#v, want %#v", got, want)
	}
}

func TestModelDeepCopiesInputAndOutput(t *testing.T) {
	input := []installmodel.ComponentSpec{{
		ID:           "component",
		Dependencies: []domain.ComponentID{"dependency"},
		Artifacts: []installmodel.ArtifactSpec{{
			HomePath: "home/file", SourcePath: "source/file", LegacyTargetSuffixes: []domain.ArtifactPath{"legacy/file"},
		}},
	}, {ID: "dependency"}}
	model, err := installmodel.New(input)
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	input[0].Dependencies[0] = "changed"
	input[0].Artifacts[0].HomePath = "changed"
	input[0].Artifacts[0].LegacyTargetSuffixes[0] = "changed"
	first := model.Artifacts()
	first[0].HomePath = "returned-change"
	first[0].LegacyTargetSuffixes[0] = "returned-change"

	got := model.Artifacts()
	if got[0].HomePath != "home/file" || got[0].LegacyTargetSuffixes[0] != "legacy/file" {
		t.Fatalf("model changed through external slice: %#v", got[0])
	}
	closure, err := model.Catalog().DependencyClosure([]domain.ComponentID{"component"})
	if err != nil || !reflect.DeepEqual(closure, []domain.ComponentID{"component", "dependency"}) {
		t.Fatalf("closure = %v, error = %v", closure, err)
	}
}

func TestModelRejectsInvalidDefinitions(t *testing.T) {
	invalidUTF8 := domain.ArtifactPath(string([]byte{0xff}))
	tests := []struct {
		name       string
		components []installmodel.ComponentSpec
		message    string
	}{
		{name: "empty component", components: []installmodel.ComponentSpec{{}}, message: "component ID"},
		{name: "duplicate component", components: []installmodel.ComponentSpec{{ID: "a"}, {ID: "a"}}, message: "duplicate component"},
		{name: "invalid home", components: componentWithArtifact("../home", "source/file", nil), message: "home path"},
		{name: "invalid UTF-8 home", components: componentWithArtifact(invalidUTF8, "source/file", nil), message: "home path"},
		{name: "noncanonical home", components: componentWithArtifact("home/../file", "source/file", nil), message: "home path"},
		{name: "invalid source", components: componentWithArtifact("home/file", "/source", nil), message: "source path"},
		{name: "noncanonical source", components: componentWithArtifact("home/file", "source//file", nil), message: "source path"},
		{name: "invalid legacy", components: componentWithArtifact("home/file", "source/file", []domain.ArtifactPath{"../legacy"}), message: "legacy target suffix"},
		{name: "duplicate home", components: []installmodel.ComponentSpec{
			{ID: "a", Artifacts: []installmodel.ArtifactSpec{{HomePath: "shared", SourcePath: "source/a"}}},
			{ID: "b", Artifacts: []installmodel.ArtifactSpec{{HomePath: "shared", SourcePath: "source/b"}}},
		}, message: "duplicate artifact path"},
		{name: "nested home", components: []installmodel.ComponentSpec{
			{ID: "a", Artifacts: []installmodel.ArtifactSpec{{HomePath: ".codex", SourcePath: "source/a"}}},
			{ID: "b", Artifacts: []installmodel.ArtifactSpec{{HomePath: ".codex/AGENTS.md", SourcePath: "source/b"}}},
		}, message: "overlapping artifact paths"},
		{name: "parent after child", components: []installmodel.ComponentSpec{
			{ID: "a", Artifacts: []installmodel.ArtifactSpec{{HomePath: ".codex/AGENTS.md", SourcePath: "source/a"}}},
			{ID: "b", Artifacts: []installmodel.ArtifactSpec{{HomePath: ".codex", SourcePath: "source/b"}}},
		}, message: "overlapping artifact paths"},
		{name: "nonportable Unicode home", components: componentWithArtifact("é/file", "source/file", nil), message: "home path"},
		{name: "nonportable Unicode source", components: componentWithArtifact("home/file", "source/é", nil), message: "source path"},
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

func componentWithArtifact(home, source domain.ArtifactPath, legacy []domain.ArtifactPath) []installmodel.ComponentSpec {
	return []installmodel.ComponentSpec{{
		ID:        "component",
		Artifacts: []installmodel.ArtifactSpec{{HomePath: home, SourcePath: source, LegacyTargetSuffixes: legacy}},
	}}
}
