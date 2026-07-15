package catalog_test

import (
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
	assertComponentIDs(t, closure, want)
}

func TestCatalogRejectsUnknownDependency(t *testing.T) {
	_, err := catalog.New([]catalog.Component{{ID: "codex-gates", Dependencies: []domain.ComponentID{"missing"}}})
	if err == nil || !strings.Contains(err.Error(), "unknown component") {
		t.Fatalf("expected unknown component error, got %v", err)
	}
}

func TestCatalogRejectsDependencyCycle(t *testing.T) {
	_, err := catalog.New([]catalog.Component{
		{ID: "a", Dependencies: []domain.ComponentID{"b"}},
		{ID: "b", Dependencies: []domain.ComponentID{"a"}},
	})
	if err == nil || !strings.Contains(err.Error(), "dependency cycle") {
		t.Fatalf("expected dependency cycle error, got %v", err)
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

func TestCatalogRejectsDuplicateArtifactOwnership(t *testing.T) {
	tests := []struct {
		name       string
		components []catalog.Component
	}{
		{
			name: "within component",
			components: []catalog.Component{{
				ID: "codex", Artifacts: []domain.Artifact{{Path: "shared"}, {Path: "shared"}},
			}},
		},
		{
			name: "across components",
			components: []catalog.Component{
				{ID: "codex", Artifacts: []domain.Artifact{{Path: "shared"}}},
				{ID: "claude-code", Artifacts: []domain.Artifact{{Path: "shared"}}},
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := catalog.New(tt.components)
			if err == nil || !strings.Contains(err.Error(), "duplicate artifact path") {
				t.Fatalf("expected duplicate artifact path error, got %v", err)
			}
		})
	}
}

func TestCatalogRejectsEmptyArtifactPath(t *testing.T) {
	_, err := catalog.New([]catalog.Component{{
		ID:        "component",
		Artifacts: []domain.Artifact{{Path: ""}},
	}})
	if err == nil || !strings.Contains(err.Error(), "artifact path must not be empty") {
		t.Fatalf("expected empty artifact path error, got %v", err)
	}
}

func TestCatalogRejectsUnsafeArtifactPaths(t *testing.T) {
	for _, artifactPath := range []string{"/absolute", "../outside", "a/../b", "a//b", ".", `a\b`, "line\nbreak"} {
		t.Run(artifactPath, func(t *testing.T) {
			_, err := catalog.New([]catalog.Component{{
				ID:        "component",
				Artifacts: []domain.Artifact{{Path: domain.ArtifactPath(artifactPath)}},
			}})
			if err == nil || !strings.Contains(err.Error(), "invalid artifact path") {
				t.Fatalf("expected invalid artifact path error, got %v", err)
			}
		})
	}
}

func TestCatalogCopiesInputAndReturnedComponents(t *testing.T) {
	components := []catalog.Component{
		{ID: "gates", Dependencies: []domain.ComponentID{"detectors"}, Artifacts: []domain.Artifact{{Path: "gate"}}},
		{ID: "detectors", Artifacts: []domain.Artifact{{Path: "detector"}}},
	}
	registry, err := catalog.New(components)
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	components[0].Dependencies[0] = "mutated"
	components[0].Artifacts[0].Path = "mutated"
	returned, _ := registry.Component("gates")
	returned.Dependencies[0] = "returned-mutation"
	returned.Artifacts[0].Path = "returned-mutation"

	closure, err := registry.DependencyClosure([]domain.ComponentID{"gates"})
	if err != nil {
		t.Fatalf("dependency closure: %v", err)
	}
	assertComponentIDs(t, closure, []domain.ComponentID{"detectors", "gates"})
	got, _ := registry.Component("gates")
	if got.Artifacts[0].Path != "gate" {
		t.Fatalf("stored artifact path = %q, want gate", got.Artifacts[0].Path)
	}
}

func assertComponentIDs(t *testing.T, got, want []domain.ComponentID) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("component count = %d, want %d: %v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("component[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}
