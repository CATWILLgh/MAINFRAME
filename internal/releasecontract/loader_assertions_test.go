package releasecontract_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func assertInstallModel(t *testing.T, release releasecontract.Release) {
	t.Helper()
	artifacts := release.Model.Artifacts()
	if len(artifacts) != 2 {
		t.Fatalf("artifact count = %d, want 2", len(artifacts))
	}
	desired, legacy := artifacts[0], artifacts[1]
	if desired.LegacyOnly {
		desired, legacy = legacy, desired
	}
	if desired.ComponentID != domain.ComponentCodex || desired.Target != location("payload.txt") {
		t.Fatalf("desired artifact = %#v", desired)
	}
	if desired.UnitID != "codex.payload" {
		t.Fatalf("desired unit ID = %q", desired.UnitID)
	}
	if desired.SourcePath != "bundles/codex/payload.txt" {
		t.Fatalf("desired source = %q", desired.SourcePath)
	}
	component, exists := release.Model.Catalog().Component(domain.ComponentCodex)
	if !exists || len(component.Artifacts) != 1 || component.Artifacts[0].UnitID != "codex.payload" {
		t.Fatalf("catalog component = %#v, exists = %t", component, exists)
	}
	if !reflect.DeepEqual(desired.LegacyTargetSuffixes, []domain.ArtifactPath{"dist/codex/payload.txt"}) {
		t.Fatalf("desired legacy suffixes = %v", desired.LegacyTargetSuffixes)
	}
	if !legacy.LegacyOnly || legacy.Target != location("obsolete.txt") {
		t.Fatalf("legacy artifact = %#v", legacy)
	}
}

func assertResourceInventory(t *testing.T, release releasecontract.Release) {
	t.Helper()
	if len(release.Resources) != 1 {
		t.Fatalf("resource count = %d", len(release.Resources))
	}
	resource := release.Resources[0]
	if resource.ID != "codex.configuration" || resource.ComponentID != domain.ComponentCodex {
		t.Fatalf("resource = %#v", resource)
	}
	if resource.SourcePath != "bundles/codex/config.json" ||
		resource.Strategy != releasecontract.StrategyJSONKeyMerge {
		t.Fatalf("resource source/strategy = %#v", resource)
	}
	if !reflect.DeepEqual(
		resource.LegacySourceSuffixes,
		[]domain.ArtifactPath{"dist/codex/config.json"},
	) {
		t.Fatalf("resource legacy sources = %v", resource.LegacySourceSuffixes)
	}
	if resource.Observation != releasecontract.SupportUnimplemented ||
		resource.Apply != releasecontract.SupportUnimplemented {
		t.Fatalf("resource support = %#v", resource)
	}
}
