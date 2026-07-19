//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestNewRecoveryPinsOnlyReferencedTargets(t *testing.T) {
	valid := canonicalTempDir(t)
	blocker := filepath.Join(canonicalTempDir(t), "file")
	if err := os.WriteFile(blocker, []byte("not a directory"), 0o600); err != nil {
		t.Fatalf("write blocker: %v", err)
	}
	workspace, err := NewRecovery(map[domain.RootID]string{
		domain.RootCodexConfig:    valid,
		domain.RootOpenCodeConfig: filepath.Join(blocker, "child"),
		domain.RootClaudeConfig:   "relative-unused",
	})
	if err != nil {
		t.Fatalf("NewRecovery() error = %v", err)
	}

	if _, err := workspace.PlanDirectories(recoveryPlan(domain.RootCodexConfig)); err != nil {
		t.Fatalf("PlanDirectories(valid) error = %v", err)
	}
	if _, err := workspace.PlanDirectories(recoveryPlan(domain.RootOpenCodeConfig)); err == nil {
		t.Fatal("PlanDirectories(invalid) accepted an unusable referenced target")
	}
}

func TestNewRecoveryRejectsInvalidTargetDefinitions(t *testing.T) {
	if _, err := NewRecovery(map[domain.RootID]string{
		"Bad Root": "/tmp",
	}); err == nil {
		t.Fatal("NewRecovery() accepted an invalid root definition")
	}
}

func TestNewRecoveryRejectsInvalidPathOnlyWhenReferenced(t *testing.T) {
	tests := []struct {
		name string
		path string
	}{
		{name: "relative", path: "relative"},
		{name: "unclean", path: "/tmp/one/../one"},
		{name: "NUL", path: "/tmp/one\x00two"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			workspace, err := NewRecovery(map[domain.RootID]string{
				domain.RootCodexConfig: test.path,
			})
			if err != nil {
				t.Fatalf("NewRecovery() error = %v", err)
			}
			if _, err := workspace.PlanDirectories(
				recoveryPlan(domain.RootCodexConfig),
			); err == nil {
				t.Fatal("PlanDirectories() accepted an invalid referenced path")
			}
		})
	}
}

func recoveryPlan(root domain.RootID) domain.Plan {
	return domain.Plan{Operations: []domain.Operation{{
		ComponentID: domain.ComponentCodex,
		Kind:        domain.OperationInstall,
		Artifact: domain.Artifact{Location: domain.Location{
			Root: root,
			Path: "AGENTS.md",
		}},
		SourcePath: "codex/AGENTS.md",
	}}}
}
