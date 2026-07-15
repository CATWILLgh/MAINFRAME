package installmanifest_test

import (
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"sort"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmanifest"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestBuiltinDefinesStableDesiredArtifacts(t *testing.T) {
	model := stableModel(t)
	want := []installmodel.Artifact{
		desired(domain.ComponentClaudeCode, domain.RootClaudeConfig, "CLAUDE.md", "dist/claude-code/CLAUDE.md", "export/CLAUDE.md"),
		desired(domain.ComponentClaudeCode, domain.RootClaudeConfig, "settings.json", "dist/claude-code/settings.json", "export/settings.json"),
		desired(domain.ComponentClaudeCode, domain.RootClaudeConfig, "skills/mainframe", "dist/claude-code/plugin", "plugin-dist"),
		desired(domain.ComponentCodex, domain.RootCodexConfig, "AGENTS.md", "dist/codex/AGENTS.md"),
		desired(domain.ComponentOpenCode, domain.RootOpenCodeConfig, "AGENTS.md", "dist/opencode/AGENTS.md", "export/AGENTS.md"),
		desired(domain.ComponentClaudeCode, domain.RootUserBin, "secret", "dist/claude-code/scripts/secret", "export/scripts/secret"),
	}
	if got := desiredArtifacts(model.Artifacts()); !reflect.DeepEqual(got, want) {
		t.Fatalf("desired artifacts = %#v, want %#v", got, want)
	}
}

func TestBuiltinPreservesExactComponentGraph(t *testing.T) {
	model := stableModel(t)
	wantDependencies := map[domain.ComponentID][]domain.ComponentID{
		domain.ComponentClaudeCode:          nil,
		domain.ComponentCodex:               nil,
		domain.ComponentOpenCode:            nil,
		domain.ComponentCodexGates:          {domain.ComponentSharedGateDetectors},
		domain.ComponentSharedGateDetectors: nil,
	}
	for id, want := range wantDependencies {
		component, exists := model.Catalog().Component(id)
		if !exists {
			t.Fatalf("component %q missing", id)
		}
		if !reflect.DeepEqual(component.Dependencies, want) {
			t.Fatalf("component %q dependencies = %v, want %v", id, component.Dependencies, want)
		}
	}
}

func TestBuiltinDefinesOnlyProvenClaudeLegacyTargets(t *testing.T) {
	model := stableModel(t)
	wantTargets := historicalClaudeTargets()
	got := legacyArtifacts(model.Artifacts())
	if len(got) != len(wantTargets) {
		t.Fatalf("legacy artifact count = %d, want %d", len(got), len(wantTargets))
	}
	for index, target := range wantTargets {
		artifact := got[index]
		wantLocation := domain.Location{Root: domain.RootClaudeConfig, Path: domain.ArtifactPath(target)}
		wantSuffix := domain.ArtifactPath("export/" + target)
		if artifact.ComponentID != domain.ComponentClaudeCode || artifact.Target != wantLocation {
			t.Fatalf("legacy artifact %d = %#v, want target %#v", index, artifact, wantLocation)
		}
		if artifact.SourcePath != "" || !artifact.LegacyOnly || !reflect.DeepEqual(artifact.LegacyTargetSuffixes, []domain.ArtifactPath{wantSuffix}) {
			t.Fatalf("legacy artifact %q broadens ownership: %#v", target, artifact)
		}
	}
	if gotCount := len(model.Artifacts()); gotCount != 6+len(wantTargets) {
		t.Fatalf("total artifact count = %d, want %d", gotCount, 6+len(wantTargets))
	}
}

func TestBuiltinDesiredSourcesExistFromRepositoryRoot(t *testing.T) {
	model := stableModel(t)
	_, testFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test file")
	}
	repositoryRoot := filepath.Clean(filepath.Join(filepath.Dir(testFile), "..", ".."))
	for _, artifact := range desiredArtifacts(model.Artifacts()) {
		path := filepath.Join(repositoryRoot, filepath.FromSlash(string(artifact.SourcePath)))
		if _, err := os.Stat(path); err != nil {
			t.Errorf("source %q: %v", artifact.SourcePath, err)
		}
	}
}

func TestBuiltinModelsAreDeeplyIndependent(t *testing.T) {
	first := installmanifest.StableComponents()
	first[0].Artifacts[0].Target.Path = "changed"
	first[0].Artifacts[0].LegacyTargetSuffixes[0] = "changed"
	first[0].LegacyArtifacts[0].TargetSuffixes[0] = "changed"

	second := stableModel(t)
	got := desiredArtifacts(second.Artifacts())[0]
	if got.Target.Path != "CLAUDE.md" || got.SourcePath != "dist/claude-code/CLAUDE.md" || got.LegacyTargetSuffixes[0] != got.SourcePath {
		t.Fatalf("second builtin manifest was mutated: %#v", got)
	}
}

func stableModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New(installmanifest.StableComponents())
	if err != nil {
		t.Fatalf("stable manifest: %v", err)
	}
	return model
}

func desired(component domain.ComponentID, root domain.RootID, target, source string, historical ...string) installmodel.Artifact {
	suffixes := []domain.ArtifactPath{domain.ArtifactPath(source)}
	for _, suffix := range historical {
		suffixes = append(suffixes, domain.ArtifactPath(suffix))
	}
	return installmodel.Artifact{
		ComponentID:          component,
		Target:               domain.Location{Root: root, Path: domain.ArtifactPath(target)},
		SourcePath:           domain.ArtifactPath(source),
		LegacyTargetSuffixes: suffixes,
	}
}

func desiredArtifacts(artifacts []installmodel.Artifact) []installmodel.Artifact {
	result := make([]installmodel.Artifact, 0, 6)
	for _, artifact := range artifacts {
		if !artifact.LegacyOnly {
			result = append(result, artifact)
		}
	}
	return result
}

func legacyArtifacts(artifacts []installmodel.Artifact) []installmodel.Artifact {
	var result []installmodel.Artifact
	for _, artifact := range artifacts {
		if artifact.LegacyOnly {
			result = append(result, artifact)
		}
	}
	return result
}

func historicalClaudeTargets() []string {
	targets := []string{
		"skills/code-audit", "skills/curl-requests", "skills/git-conventional-commits-ru", "skills/nestjs-backend-patterns",
		"skills/no-suppression-markers", "skills/ops-app-server-safety", "skills/python-backend-patterns",
		"skills/react-frontend-patterns", "skills/secrets-handling", "skills/severity-calibration", "skills/shadcn",
		"skills/surface-ticket", "skills/task-workflow", "skills/testing-strategy",
		"agents/nestjs-backend-engineer.md", "agents/python-backend-engineer.md",
		"agents/react-frontend-engineer.md", "agents/web-search.md",
		"hooks/bash-pattern-reminder.py", "hooks/comment-discipline-reminder.py", "hooks/frontend-dead-code.py",
		"hooks/frontend-fsd-gate.py", "hooks/nodejs-deps-audit.py", "hooks/nodejs-security-scan.py",
		"hooks/nodejs-security-stop-gate.py", "hooks/path-validation.py", "hooks/python-deps-audit.py",
		"hooks/python-security-scan.py", "hooks/python-security-stop-gate.py", "hooks/scan-suppression-markers.py",
		"hooks/stop-gate-suppression-markers.py", "hooks/rules",
	}
	sort.Strings(targets)
	return targets
}
