package catalog_test

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestDependencyClosureIncludesOnlyDeclaredDependencies(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude-code"},
		{ID: "codex"},
		{ID: "codex-gates", Dependencies: []domain.ComponentID{"shared-gate-detectors"}},
		{ID: "shared-gate-detectors"},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	closure, err := registry.DependencyClosure([]domain.ComponentID{"codex", "codex-gates"})
	if err != nil {
		t.Fatalf("dependency closure: %v", err)
	}
	want := []domain.ComponentID{"codex", "codex-gates", "shared-gate-detectors"}
	if !reflect.DeepEqual(closure, want) {
		t.Fatalf("closure = %v, want %v", closure, want)
	}
}

func TestCatalogRejectsInvalidDependencies(t *testing.T) {
	tests := []struct {
		name       string
		components []catalog.Component
		message    string
	}{
		{name: "unknown", components: []catalog.Component{{ID: "a", Dependencies: []domain.ComponentID{"missing"}}}, message: "unknown component"},
		{name: "cycle", components: []catalog.Component{{ID: "a", Dependencies: []domain.ComponentID{"b"}}, {ID: "b", Dependencies: []domain.ComponentID{"a"}}}, message: "dependency cycle"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := catalog.New(tt.components)
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestDependencyClosureRejectsUnknownRequestedComponent(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{{ID: "claude-code"}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	_, err = registry.DependencyClosure([]domain.ComponentID{"unknown"})
	if err == nil || !strings.Contains(err.Error(), "unknown component") {
		t.Fatalf("expected unknown component error, got %v", err)
	}
}

func TestCatalogKeepsSamePathUnderDifferentRootsDistinct(t *testing.T) {
	registry, err := catalog.New([]catalog.Component{
		{ID: "claude", Artifacts: []catalog.Artifact{expected(domain.RootClaudeConfig, "AGENTS.md", "dist/claude/AGENTS.md")}},
		{ID: "codex", Artifacts: []catalog.Artifact{expected(domain.RootCodexConfig, "AGENTS.md", "dist/codex/AGENTS.md")}},
	})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	for _, id := range []domain.ComponentID{"claude", "codex"} {
		component, exists := registry.Component(id)
		if !exists || len(component.Artifacts) != 1 {
			t.Fatalf("component %q = %#v, exists = %v", id, component, exists)
		}
	}
}

func TestCatalogRejectsDuplicateTarget(t *testing.T) {
	target := expected(domain.RootCodexConfig, "shared", "source/a")
	_, err := catalog.New([]catalog.Component{
		{ID: "a", Artifacts: []catalog.Artifact{target}},
		{ID: "b", Artifacts: []catalog.Artifact{{Target: target.Target, SourcePath: "source/b"}}},
	})
	if err == nil || !strings.Contains(err.Error(), "duplicate artifact target") {
		t.Fatalf("expected duplicate target error, got %v", err)
	}
}

func TestCatalogRejectsInvalidArtifactContract(t *testing.T) {
	tests := []struct {
		name     string
		artifact catalog.Artifact
		message  string
	}{
		{name: "empty root", artifact: catalog.Artifact{Target: domain.Location{Path: "file"}, SourcePath: "source/file"}, message: "invalid artifact target"},
		{name: "invalid root", artifact: catalog.Artifact{Target: domain.Location{Root: "Invalid", Path: "file"}, SourcePath: "source/file"}, message: "invalid artifact target"},
		{name: "empty target path", artifact: catalog.Artifact{Target: domain.Location{Root: domain.RootHome}, SourcePath: "source/file"}, message: "invalid artifact target"},
		{name: "unsafe target path", artifact: catalog.Artifact{Target: domain.Location{Root: domain.RootHome, Path: "../file"}, SourcePath: "source/file"}, message: "invalid artifact target"},
		{name: "non-portable target path", artifact: catalog.Artifact{Target: loc(domain.RootHome, "é/file"), SourcePath: "source/file"}, message: "invalid artifact target"},
		{name: "empty source", artifact: catalog.Artifact{Target: loc(domain.RootHome, "file")}, message: "invalid source path"},
		{name: "unsafe source", artifact: catalog.Artifact{Target: loc(domain.RootHome, "file"), SourcePath: "../source"}, message: "invalid source path"},
		{name: "non-portable source", artifact: catalog.Artifact{Target: loc(domain.RootHome, "file"), SourcePath: "source/é"}, message: "invalid source path"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := catalog.New([]catalog.Component{{ID: "component", Artifacts: []catalog.Artifact{tt.artifact}}})
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestCatalogCopiesInputAndReturnedComponents(t *testing.T) {
	components := []catalog.Component{
		{ID: "gates", Dependencies: []domain.ComponentID{"detectors"}, Artifacts: []catalog.Artifact{expected(domain.RootCodexConfig, "gate", "source/gate")}},
		{ID: "detectors", Artifacts: []catalog.Artifact{expected(domain.RootCommonData, "detector", "source/detector")}},
	}
	registry, err := catalog.New(components)
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	components[0].Dependencies[0] = "mutated"
	components[0].Artifacts[0].Target.Path = "mutated"
	returned, _ := registry.Component("gates")
	returned.Dependencies[0] = "returned-mutation"
	returned.Artifacts[0].SourcePath = "returned-mutation"

	closure, err := registry.DependencyClosure([]domain.ComponentID{"gates"})
	if err != nil || !reflect.DeepEqual(closure, []domain.ComponentID{"detectors", "gates"}) {
		t.Fatalf("closure = %v, error = %v", closure, err)
	}
	got, _ := registry.Component("gates")
	if got.Artifacts[0] != expected(domain.RootCodexConfig, "gate", "source/gate") {
		t.Fatalf("stored artifact = %#v", got.Artifacts[0])
	}
}

func expected(root domain.RootID, target, source domain.ArtifactPath) catalog.Artifact {
	return catalog.Artifact{Target: loc(root, target), SourcePath: source}
}

func loc(root domain.RootID, artifactPath domain.ArtifactPath) domain.Location {
	return domain.Location{Root: root, Path: artifactPath}
}
