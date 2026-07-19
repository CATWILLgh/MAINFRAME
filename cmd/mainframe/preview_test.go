package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewServiceDiscoversExactArtifactAsAdoptable(t *testing.T) {
	releaseRoot := t.TempDir()
	source := writeCodexInstructions(t, releaseRoot, "instructions\n")
	configureCodexPreviewHome(t, source)
	service, err := buildPreviewServiceFrom(releaseRoot, releasecontract.Release{
		ID: "test-release", Model: codexInstructionsModel(t),
		Resources: adoptionPreviewResources(),
	})
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	assertCodexAdoptionPreview(t, service)
}

func assertCodexAdoptionPreview(t *testing.T, service lifecycle.Service) {
	t.Helper()
	targets := service.Targets()
	for _, target := range targets {
		if target.ID == domain.ComponentCodex {
			if target.Status != lifecycle.StatusAttention || !target.Selected {
				t.Fatalf("Codex target = %#v", target)
			}
			if len(target.Configuration) != 2 ||
				target.Configuration[0].Status != lifecycle.ConfigurationNeedsChange ||
				target.Configuration[1].Status != lifecycle.ConfigurationReady {
				t.Fatalf("Codex configuration = %#v", target.Configuration)
			}
			preview, err := service.Preview(lifecycle.PreviewRequest{
				Components: []domain.ComponentID{domain.ComponentCodex},
			})
			if err != nil {
				t.Fatalf("preview adoption: %v", err)
			}
			operations := preview.Filesystem.Operations
			if len(operations) != 1 || operations[0].Kind != domain.OperationAdopt {
				t.Fatalf("adoption operations = %#v", operations)
			}
			return
		}
	}
	t.Fatal("Codex target not found")
}

func TestBuildPreviewServiceRejectsInvalidExplicitSource(t *testing.T) {
	t.Setenv(releaseRootEnvironment, t.TempDir())
	t.Setenv("HOME", t.TempDir())

	_, err := buildPreviewService()
	if err == nil {
		t.Fatal("invalid explicit source root was accepted")
	}
}

func TestBuildPreviewServicePlansRegistryBackedReleaseReplacement(t *testing.T) {
	releaseRoot := canonicalTempDir(t)
	writeCodexInstructions(t, releaseRoot, "new\n")
	oldRoot := canonicalTempDir(t)
	oldSource := writeCodexInstructions(t, oldRoot, "old\n")
	configureCodexPreviewHome(t, oldSource)
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	saveCodexOwnership(t, stateBase, oldSource)
	t.Setenv("XDG_STATE_HOME", stateBase)

	service, err := buildPreviewServiceFrom(releaseRoot, releasecontract.Release{
		ID: "new-release", IndexSHA256: applyRuntimeDigest(2), Model: codexInstructionsModel(t),
	})
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	preview, err := service.Preview(lifecycle.PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentCodex},
	})
	if err != nil {
		t.Fatalf("preview replacement: %v", err)
	}
	operations := preview.Filesystem.Operations
	if len(operations) != 1 || operations[0].Kind != domain.OperationReplace ||
		operations[0].UnitID != "codex.instructions" {
		t.Fatalf("replacement operations = %#v", operations)
	}
}

func writeCodexInstructions(t *testing.T, root, content string) string {
	t.Helper()
	source := filepath.Join(root, "bundles", "codex", "AGENTS.md")
	if err := os.MkdirAll(filepath.Dir(source), 0o755); err != nil {
		t.Fatalf("mkdir release source: %v", err)
	}
	if err := os.WriteFile(source, []byte(content), 0o644); err != nil {
		t.Fatalf("write release source: %v", err)
	}
	canonical, err := filepath.EvalSymlinks(source)
	if err != nil {
		t.Fatalf("resolve release source: %v", err)
	}
	return canonical
}

func configureCodexPreviewHome(t *testing.T, source string) (string, string) {
	t.Helper()
	home := canonicalTempDir(t)
	codex := filepath.Join(home, ".codex")
	if err := os.MkdirAll(codex, 0o755); err != nil {
		t.Fatalf("mkdir Codex root: %v", err)
	}
	if err := os.Symlink(source, filepath.Join(codex, "AGENTS.md")); err != nil {
		t.Fatalf("link Codex artifact: %v", err)
	}
	if err := os.WriteFile(filepath.Join(home, ".zshenv"), []byte("source ~/.config/mainframe/env\n"), 0o600); err != nil {
		t.Fatalf("write shell profile: %v", err)
	}
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", codex)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))
	return home, codex
}

func codexInstructionsModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{{
				UnitID:     "codex.instructions",
				Target:     domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
				SourcePath: "bundles/codex/AGENTS.md",
			}},
		},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	return model
}

func adoptionPreviewResources() []releasecontract.Resource {
	return []releasecontract.Resource{
		{
			ID: "codex.credentials-index", ComponentID: domain.ComponentCodex,
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Target:      domain.Location{Root: domain.RootCodexConfig, Path: "credentials-index.md"},
			Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportUnimplemented,
		},
		{
			ID: "codex.zshenv-source", ComponentID: domain.ComponentCodex,
			Strategy:    releasecontract.StrategyShellLine,
			Target:      domain.Location{Root: domain.RootHome, Path: ".zshenv"},
			Observation: releasecontract.SupportSupported, Apply: releasecontract.SupportUnimplemented,
			DesiredLine: "source ~/.config/mainframe/env",
		},
	}
}

func saveCodexOwnership(t *testing.T, stateBase, source string) {
	t.Helper()
	state, err := executor.OpenUnixState(filepath.Join(stateBase, "mainframe"))
	if err != nil {
		t.Fatalf("open state: %v", err)
	}
	registry, err := linkownership.New([]linkownership.Claim{{
		UnitID: "codex.instructions", ComponentID: domain.ComponentCodex,
		Target:    domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
		RawTarget: source, ReleaseID: "old-release", IndexSHA256: applyRuntimeDigest(1),
	}})
	if err != nil {
		t.Fatalf("new ownership registry: %v", err)
	}
	if err := state.SaveOwnership(registry); err != nil {
		t.Fatalf("save ownership registry: %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("close state: %v", err)
	}
}

func TestResolveReleaseRootRejectsEmptyExplicitValue(t *testing.T) {
	t.Setenv(releaseRootEnvironment, "")
	if _, err := resolveReleaseRoot(); err == nil {
		t.Fatal("empty explicit source root was accepted")
	}
}
