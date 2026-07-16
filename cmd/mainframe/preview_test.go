package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewServiceDiscoversManagedArtifact(t *testing.T) {
	releaseRoot := t.TempDir()
	source := filepath.Join(releaseRoot, "bundles/codex/AGENTS.md")
	if err := os.MkdirAll(filepath.Dir(source), 0o755); err != nil {
		t.Fatalf("mkdir release source: %v", err)
	}
	if err := os.WriteFile(source, []byte("instructions\n"), 0o644); err != nil {
		t.Fatalf("write release source: %v", err)
	}
	canonicalSource, err := filepath.EvalSymlinks(source)
	if err != nil {
		t.Fatalf("resolve release source: %v", err)
	}
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{
				{
					Target: domain.Location{
						Root: domain.RootCodexConfig,
						Path: "AGENTS.md",
					},
					SourcePath: "bundles/codex/AGENTS.md",
				},
			},
		},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	home := t.TempDir()
	codex := filepath.Join(home, ".codex")
	if err := os.MkdirAll(codex, 0o755); err != nil {
		t.Fatalf("mkdir Codex root: %v", err)
	}
	if err := os.Symlink(
		canonicalSource,
		filepath.Join(codex, "AGENTS.md"),
	); err != nil {
		t.Fatalf("link Codex artifact: %v", err)
	}
	if err := os.WriteFile(filepath.Join(home, ".zshenv"), []byte("source ~/.config/mainframe/env\n"), 0o600); err != nil {
		t.Fatalf("write shell profile: %v", err)
	}
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", codex)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))

	service, err := buildPreviewServiceFrom(
		releaseRoot,
		releasecontract.Release{
			ID: "test-release", Model: model,
			Resources: []releasecontract.Resource{
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
			},
		},
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	targets := service.Targets()
	for _, target := range targets {
		if target.ID == domain.ComponentCodex {
			if target.Status != lifecycle.StatusManaged || !target.Selected {
				t.Fatalf("Codex target = %#v", target)
			}
			if len(target.Configuration) != 2 ||
				target.Configuration[0].Status != lifecycle.ConfigurationNeedsChange ||
				target.Configuration[1].Status != lifecycle.ConfigurationReady {
				t.Fatalf("Codex configuration = %#v", target.Configuration)
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

func TestResolveReleaseRootRejectsEmptyExplicitValue(t *testing.T) {
	t.Setenv(releaseRootEnvironment, "")
	if _, err := resolveReleaseRoot(); err == nil {
		t.Fatal("empty explicit source root was accepted")
	}
}
