package plan_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

func TestPlannerPreservesSelectedClaimedWritableDriftAndMissing(t *testing.T) {
	const digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	driftedLocation := location(domain.RootCodexConfig, "agents/drifted.md")
	missingLocation := location(domain.RootCodexConfig, "agents/missing.md")
	registry, err := catalog.New([]catalog.Component{{
		ID: "codex",
		Artifacts: []catalog.Artifact{
			{UnitID: "codex.drifted", Materialization: domain.MaterializationWritableFile, Target: driftedLocation, SourcePath: "agents/drifted.md", SourceSHA256: digest},
			{UnitID: "codex.missing", Materialization: domain.MaterializationWritableFile, Target: missingLocation, SourcePath: "agents/missing.md", SourceSHA256: digest},
		},
	}})
	if err != nil {
		t.Fatalf("catalog.New() error = %v", err)
	}
	drifted := domain.Artifact{
		Location: driftedLocation, UnitID: "codex.drifted",
		Ownership:       domain.OwnershipManagedDrifted,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   digest, Mode: 0o600,
	}
	missing := domain.Artifact{
		Location: missingLocation, UnitID: "codex.missing",
		Ownership:       domain.OwnershipManagedMissing,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   digest, Mode: 0o600,
	}
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{drifted, missing},
		}}},
	}

	first, err := plan.New(registry).Plan(request)
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	second, err := plan.New(registry).Plan(request)
	if err != nil {
		t.Fatalf("repeated Plan() error = %v", err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("repeated plan changed: first=%#v second=%#v", first, second)
	}
	assertOperations(t, first.Operations, []domain.Operation{
		{ComponentID: "codex", UnitID: "codex.drifted", Kind: domain.OperationPreserve, Artifact: drifted},
		{ComponentID: "codex", UnitID: "codex.missing", Kind: domain.OperationPreserve, Artifact: missing},
	})
}

func TestPlannerDoesNotPreserveForeignOrSymlinkArtifacts(t *testing.T) {
	const digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	target := location(domain.RootCodexConfig, "agents/agent.md")
	registry, err := catalog.New([]catalog.Component{{ID: "codex", Artifacts: []catalog.Artifact{{
		UnitID: "codex.agent", Materialization: domain.MaterializationWritableFile,
		Target: target, SourcePath: "agents/agent.md", SourceSHA256: digest,
	}}}})
	if err != nil {
		t.Fatalf("catalog.New() error = %v", err)
	}
	tests := []struct {
		name     string
		artifact domain.Artifact
	}{
		{name: "foreign regular file", artifact: domain.Artifact{Location: target, Ownership: domain.OwnershipConflict, Materialization: domain.MaterializationWritableFile}},
		{name: "managed symlink", artifact: domain.Artifact{Location: target, UnitID: "codex.agent", Ownership: domain.OwnershipManagedDrifted, Materialization: domain.MaterializationSymlink}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, planErr := plan.New(registry).Plan(domain.PlanRequest{
				Desired:  domain.DesiredState{Components: []domain.ComponentID{"codex"}},
				Observed: domain.ObservedState{Components: []domain.ObservedComponent{{ID: "codex", Artifacts: []domain.Artifact{test.artifact}}}},
			})
			if planErr != nil {
				t.Fatalf("Plan() error = %v", planErr)
			}
			if len(got.Operations) != 1 || got.Operations[0].Kind != domain.OperationConflict {
				t.Fatalf("operations = %#v, want one conflict", got.Operations)
			}
		})
	}
}

func TestPlannerRelinquishesDeselectedClaimedWritableDriftAndMissing(t *testing.T) {
	const digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	artifacts := []domain.Artifact{
		{Location: location(domain.RootCodexConfig, "agents/drifted.md"), UnitID: "codex.drifted", Ownership: domain.OwnershipManagedDrifted, Materialization: domain.MaterializationWritableFile, ContentSHA256: digest, Mode: 0o600},
		{Location: location(domain.RootCodexConfig, "agents/missing.md"), UnitID: "codex.missing", Ownership: domain.OwnershipManagedMissing, Materialization: domain.MaterializationWritableFile, ContentSHA256: digest, Mode: 0o600},
	}
	got, err := newPlanner(t).Plan(domain.PlanRequest{Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: "codex", Artifacts: artifacts,
	}}}})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	assertOperations(t, got.Operations, []domain.Operation{
		{ComponentID: "codex", UnitID: "codex.drifted", Kind: domain.OperationRelinquish, Artifact: artifacts[0]},
		{ComponentID: "codex", UnitID: "codex.missing", Kind: domain.OperationRelinquish, Artifact: artifacts[1]},
	})
}
