package plan_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/catalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

const migrationSHA256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func TestPlannerReplacesManagedSymlinkWithDesiredWritableFile(t *testing.T) {
	target := location(domain.RootCodexConfig, "agents/AGENT.md")
	components, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{{
			UnitID: "codex.agent", Target: target, SourcePath: "dist/AGENT.md",
			SourceSHA256: migrationSHA256, Materialization: domain.MaterializationWritableFile,
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	previous := domain.Artifact{
		Location: target, UnitID: "codex.agent",
		Ownership: domain.OwnershipManagedPrevious,
		RawTarget: "/releases/old/AGENT.md", LinkDevice: 1, LinkInode: 2,
	}
	got, err := plan.New(components).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{previous},
		}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	if len(got.Operations) != 1 || got.Operations[0].Kind != domain.OperationReplace ||
		got.Operations[0].Artifact.Materialization != domain.MaterializationWritableFile ||
		got.Operations[0].Artifact.RawTarget != previous.RawTarget ||
		got.Operations[0].SourceSHA256 != migrationSHA256 {
		t.Fatalf("operations = %#v", got.Operations)
	}
}

func TestPlannerRejectsWritableFileToSymlinkTransition(t *testing.T) {
	target := location(domain.RootCodexConfig, "agents/AGENT.md")
	components, err := catalog.New([]catalog.Component{{
		ID: "codex", Artifacts: []catalog.Artifact{{
			UnitID: "codex.agent", Target: target, SourcePath: "dist/AGENT.md",
		}},
	}})
	if err != nil {
		t.Fatalf("new catalog: %v", err)
	}
	observed := domain.Artifact{
		Location: target, UnitID: "codex.agent",
		Ownership:       domain.OwnershipManagedDrifted,
		Materialization: domain.MaterializationWritableFile,
	}
	got, err := plan.New(components).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"codex"}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: "codex", Artifacts: []domain.Artifact{observed},
		}}},
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	if len(got.Operations) != 1 || got.Operations[0].Kind != domain.OperationConflict {
		t.Fatalf("operations = %#v", got.Operations)
	}
}
