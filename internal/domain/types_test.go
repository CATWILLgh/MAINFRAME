package domain_test

import (
	"encoding/json"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPlanJSONContract(t *testing.T) {
	plan := domain.Plan{Operations: []domain.Operation{{
		ComponentID: "codex",
		Kind:        domain.OperationRemove,
		Artifact: domain.Artifact{
			Location:  domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
			Ownership: domain.OwnershipManagedExact,
		},
	}}}

	got, err := json.Marshal(plan)
	if err != nil {
		t.Fatalf("marshal plan: %v", err)
	}
	want := `{"operations":[{"component_id":"codex","kind":"remove","artifact":{"location":{"root":"codex-config","path":"AGENTS.md"},"ownership":"managed_exact"}}]}`
	if string(got) != want {
		t.Fatalf("JSON contract mismatch\nwant: %s\n got: %s", want, got)
	}
}

func TestInstallOperationJSONIncludesOnlyInstallSourcePath(t *testing.T) {
	plan := domain.Plan{Operations: []domain.Operation{
		{ComponentID: "codex", Kind: domain.OperationInstall, Artifact: domain.Artifact{Location: domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"}}, SourcePath: "dist/codex/AGENTS.md"},
		{ComponentID: "codex", Kind: domain.OperationConflict, Artifact: domain.Artifact{Location: domain.Location{Root: domain.RootCodexConfig, Path: "config.toml"}, Ownership: domain.OwnershipForeign}},
	}}
	got, err := json.Marshal(plan)
	if err != nil {
		t.Fatalf("marshal plan: %v", err)
	}
	want := `{"operations":[{"component_id":"codex","kind":"install","artifact":{"location":{"root":"codex-config","path":"AGENTS.md"}},"source_path":"dist/codex/AGENTS.md"},{"component_id":"codex","kind":"conflict","artifact":{"location":{"root":"codex-config","path":"config.toml"},"ownership":"foreign"}}]}`
	if string(got) != want {
		t.Fatalf("JSON contract mismatch\nwant: %s\n got: %s", want, got)
	}
}

func TestRootIDGrammar(t *testing.T) {
	valid := []domain.RootID{"a", "home", "a0", "a--", "a-", "credentials-config"}
	invalid := []domain.RootID{"", "A", "0a", "-a", "a_b", "a.b", "a/b", "a b"}
	for _, root := range valid {
		if !root.Valid() {
			t.Errorf("Valid(%q) = false, want true", root)
		}
	}
	for _, root := range invalid {
		if root.Valid() {
			t.Errorf("Valid(%q) = true, want false", root)
		}
	}
}

func TestArtifactPathPortableContract(t *testing.T) {
	valid := []domain.ArtifactPath{"file", ".codex/AGENTS.md", "a-b/c_1"}
	invalid := []domain.ArtifactPath{"é/file", "e\u0301/file", "../file"}
	for _, artifactPath := range valid {
		if !artifactPath.Portable() {
			t.Errorf("Portable(%q) = false, want true", artifactPath)
		}
	}
	for _, artifactPath := range invalid {
		if artifactPath.Portable() {
			t.Errorf("Portable(%q) = true, want false", artifactPath)
		}
	}
}

func TestLocationJSONAndValidity(t *testing.T) {
	location := domain.Location{Root: domain.RootHome, Path: ".config/tool"}
	if !location.Valid() {
		t.Fatal("expected location to be valid")
	}
	got, err := json.Marshal(location)
	if err != nil {
		t.Fatalf("marshal location: %v", err)
	}
	if string(got) != `{"root":"home","path":".config/tool"}` {
		t.Fatalf("location JSON = %s", got)
	}
	for _, invalid := range []domain.Location{
		{Path: "valid"},
		{Root: "Invalid", Path: "valid"},
		{Root: domain.RootHome},
		{Root: domain.RootHome, Path: "../escape"},
	} {
		if invalid.Valid() {
			t.Errorf("Valid(%#v) = true, want false", invalid)
		}
	}
}

func TestOnlyRegistryOwnedLinksAreRemovable(t *testing.T) {
	statuses := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedPrevious,
		domain.OwnershipManagedDrifted,
		domain.OwnershipManagedMissing,
		domain.OwnershipExactAdoptable,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}

	for _, status := range statuses {
		want := status == domain.OwnershipManagedExact ||
			status == domain.OwnershipManagedPrevious
		if got := status.Removable(); got != want {
			t.Errorf("Removable(%q) = %v, want %v", status, got, want)
		}
	}
}

func TestManagedOwnershipStatusesRemainRegistryBound(t *testing.T) {
	tests := map[domain.OwnershipStatus]bool{
		domain.OwnershipManagedExact:    true,
		domain.OwnershipManagedPrevious: true,
		domain.OwnershipManagedDrifted:  true,
		domain.OwnershipManagedMissing:  true,
		domain.OwnershipExactAdoptable:  false,
		domain.OwnershipLegacyAdoptable: false,
		domain.OwnershipForeign:         false,
		domain.OwnershipConflict:        false,
	}
	for status, want := range tests {
		if got := status.Managed(); got != want {
			t.Errorf("Managed(%q) = %v, want %v", status, got, want)
		}
	}
}

func TestObservedComponentIsManagedOnlyThroughAClaimedArtifact(t *testing.T) {
	component := domain.ObservedComponent{Artifacts: []domain.Artifact{
		{UnitID: "claude-code.base", Ownership: domain.OwnershipForeign},
		{Ownership: domain.OwnershipManagedExact},
	}}
	if component.Managed() {
		t.Fatal("ObservedComponent.Managed() accepted unclaimed state")
	}
	component.Artifacts = append(component.Artifacts, domain.Artifact{
		UnitID:    "claude-code.dev.harness-feedback",
		Ownership: domain.OwnershipManagedMissing,
	})
	if !component.Managed() {
		t.Fatal("ObservedComponent.Managed() rejected claimed state")
	}
}

func TestOwnershipStatusValidity(t *testing.T) {
	valid := []domain.OwnershipStatus{
		domain.OwnershipManagedExact,
		domain.OwnershipManagedDrifted,
		domain.OwnershipLegacyAdoptable,
		domain.OwnershipForeign,
		domain.OwnershipConflict,
	}
	for _, status := range valid {
		if !status.Valid() {
			t.Errorf("Valid(%q) = false, want true", status)
		}
	}
	for _, status := range []domain.OwnershipStatus{"", "unknown"} {
		if status.Valid() {
			t.Errorf("Valid(%q) = true, want false", status)
		}
	}
}
