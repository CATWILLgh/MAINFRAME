package installsource

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestFindReturnsFirstRootContainingEveryDesiredSource(t *testing.T) {
	model := sourceTestModel(t)
	missing := canonicalPath(t, t.TempDir())
	valid := canonicalPath(t, t.TempDir())
	writeSource(t, valid, "dist/claude/CLAUDE.md")
	writeSource(t, valid, "dist/codex/AGENTS.md")

	root, err := Find([]string{missing, valid}, model, os.Stat, os.Lstat)
	if err != nil {
		t.Fatalf("find: %v", err)
	}
	if root != valid {
		t.Fatalf("root = %q, want %q", root, valid)
	}
}

func TestFindRejectsRelativeAndIncompleteRoots(t *testing.T) {
	model := sourceTestModel(t)
	incomplete := canonicalPath(t, t.TempDir())
	writeSource(t, incomplete, "dist/claude/CLAUDE.md")

	_, err := Find([]string{"relative", incomplete}, model, os.Stat, os.Lstat)
	if err == nil {
		t.Fatal("incomplete roots were accepted")
	}
	for _, text := range []string{"relative", "dist/codex/AGENTS.md"} {
		if !strings.Contains(err.Error(), text) {
			t.Fatalf("error %q does not contain %q", err, text)
		}
	}
}

func TestFindIgnoresLegacyOnlySources(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				{
					Target:     domain.Location{Root: domain.RootClaudeConfig, Path: "CLAUDE.md"},
					SourcePath: "dist/claude/CLAUDE.md",
				},
			},
			LegacyArtifacts: []installmodel.LegacyArtifactSpec{
				{
					Target:         domain.Location{Root: domain.RootClaudeConfig, Path: "legacy"},
					TargetSuffixes: []domain.ArtifactPath{"old/legacy"},
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	root := canonicalPath(t, t.TempDir())
	writeSource(t, root, "dist/claude/CLAUDE.md")

	if _, err := Find([]string{root}, model, os.Stat, os.Lstat); err != nil {
		t.Fatalf("find: %v", err)
	}
}

func TestFindRejectsSymbolicLinkSourceRoot(t *testing.T) {
	model := sourceTestModel(t)
	realRoot := canonicalPath(t, t.TempDir())
	writeSource(t, realRoot, "dist/claude/CLAUDE.md")
	writeSource(t, realRoot, "dist/codex/AGENTS.md")
	alias := filepath.Join(t.TempDir(), "mainframe")
	if err := os.Symlink(realRoot, alias); err != nil {
		t.Fatalf("symlink: %v", err)
	}

	_, err := Find([]string{alias}, model, os.Stat, os.Lstat)
	if err == nil {
		t.Fatal("symbolic link source root was accepted")
	}
	if !strings.Contains(err.Error(), "must not be a symbolic link") {
		t.Fatalf("error = %q", err)
	}
}

func TestFindRejectsSourceRootBelowSymbolicLinkParent(t *testing.T) {
	model := sourceTestModel(t)
	realParent := canonicalPath(t, t.TempDir())
	realRoot := filepath.Join(realParent, "MAINFRAME")
	writeSource(t, realRoot, "dist/claude/CLAUDE.md")
	writeSource(t, realRoot, "dist/codex/AGENTS.md")
	aliasParent := filepath.Join(t.TempDir(), "alias")
	if err := os.Symlink(realParent, aliasParent); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	aliasRoot := filepath.Join(aliasParent, "MAINFRAME")

	_, err := Find([]string{aliasRoot}, model, os.Stat, os.Lstat)
	if err == nil {
		t.Fatal("source root below symbolic link parent was accepted")
	}
	if !strings.Contains(err.Error(), "symbolic links") {
		t.Fatalf("error = %q", err)
	}
}

func sourceTestModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				{
					Target:     domain.Location{Root: domain.RootClaudeConfig, Path: "CLAUDE.md"},
					SourcePath: "dist/claude/CLAUDE.md",
				},
			},
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{
				{
					Target:     domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"},
					SourcePath: "dist/codex/AGENTS.md",
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	return model
}

func writeSource(t *testing.T, root, relative string) {
	t.Helper()
	path := filepath.Join(root, relative)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(path, []byte("source"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func canonicalPath(t *testing.T, path string) string {
	t.Helper()
	canonical, err := filepath.EvalSymlinks(path)
	if err != nil {
		t.Fatalf("canonicalize %q: %v", path, err)
	}
	return canonical
}
