//go:build darwin || linux

package linkworkspace

import (
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestManagedDirectoryPlanDeduplicatesAliasedRoots(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, "shared")
	workspace, err := New(source, map[domain.RootID]string{
		domain.RootCodexConfig:    target,
		domain.RootOpenCodeConfig: target,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	plan := domain.Plan{Operations: []domain.Operation{
		installOperation(domain.RootCodexConfig, "one"),
		installOperation(domain.RootOpenCodeConfig, "two"),
	}}

	directories, err := workspace.PlanDirectories(plan)

	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	if len(directories.Roots) != 2 || len(directories.Missing) != 1 {
		t.Fatalf("directory plan = %#v", directories)
	}
	if directories.Missing[0].Target.Root != domain.RootCodexConfig {
		t.Fatalf("canonical target = %#v", directories.Missing[0].Target)
	}
}

func TestManagedDirectoryPlanRejectsAliasedPhysicalLinkTargets(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, "shared")
	workspace, err := New(source, map[domain.RootID]string{
		domain.RootCodexConfig:    target,
		domain.RootOpenCodeConfig: target,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	plan := domain.Plan{Operations: []domain.Operation{
		installOperation(domain.RootCodexConfig, "same"),
		installOperation(domain.RootOpenCodeConfig, "same"),
	}}

	if _, err := workspace.PlanDirectories(plan); err == nil {
		t.Fatal("PlanDirectories() accepted aliased physical link targets")
	}
}

func installPlan(root domain.RootID, target domain.ArtifactPath) domain.Plan {
	return domain.Plan{Operations: []domain.Operation{
		installOperation(root, target),
	}}
}

func installOperation(
	root domain.RootID,
	target domain.ArtifactPath,
) domain.Operation {
	return domain.Operation{
		ComponentID: "component",
		Kind:        domain.OperationInstall,
		Artifact: domain.Artifact{Location: domain.Location{
			Root: root,
			Path: target,
		}},
		SourcePath: "source/file",
	}
}
