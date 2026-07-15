package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestBuildPreviewServiceDiscoversManagedArtifact(t *testing.T) {
	repository := repositoryRoot(t)
	home := t.TempDir()
	codex := filepath.Join(home, ".codex")
	if err := os.MkdirAll(codex, 0o755); err != nil {
		t.Fatalf("mkdir Codex root: %v", err)
	}
	if err := os.Symlink(
		filepath.Join(repository, "dist/codex/AGENTS.md"),
		filepath.Join(codex, "AGENTS.md"),
	); err != nil {
		t.Fatalf("link Codex artifact: %v", err)
	}
	t.Setenv(sourceRootEnvironment, repository)
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", codex)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))

	service, err := buildPreviewService()
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	targets := service.Targets()
	for _, target := range targets {
		if target.ID == domain.ComponentCodex {
			if target.Status != lifecycle.StatusManaged || !target.Selected {
				t.Fatalf("Codex target = %#v", target)
			}
			return
		}
	}
	t.Fatal("Codex target not found")
}

func TestBuildPreviewServiceRejectsInvalidExplicitSource(t *testing.T) {
	t.Setenv(sourceRootEnvironment, t.TempDir())
	t.Setenv("HOME", t.TempDir())

	_, err := buildPreviewService()
	if err == nil {
		t.Fatal("invalid explicit source root was accepted")
	}
}

func TestSourceRootCandidatesRejectsEmptyExplicitValue(t *testing.T) {
	t.Setenv(sourceRootEnvironment, "")
	if _, err := sourceRootCandidates(); err == nil {
		t.Fatal("empty explicit source root was accepted")
	}
}

func repositoryRoot(t *testing.T) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("working directory: %v", err)
	}
	root := filepath.Clean(filepath.Join(workingDirectory, "../.."))
	if !filepath.IsAbs(root) {
		t.Fatalf("repository root is not absolute: %q", root)
	}
	return root
}
