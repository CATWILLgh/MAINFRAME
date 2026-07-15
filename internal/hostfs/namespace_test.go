package hostfs_test

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestOpenCanonicalizesExistingAndMissingRoots(t *testing.T) {
	base := t.TempDir()
	realHome := filepath.Join(base, "реальный-дом")
	mustMkdirAll(t, filepath.Join(realHome, "repo"))
	homeAlias := filepath.Join(base, "home-alias")
	mustSymlink(t, realHome, homeAlias)
	layout := mustLayout(t, homeAlias, filepath.Join(homeAlias, "repo", "missing", "source"), nil)

	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	roots := namespace.Roots()
	canonicalHome := evaluatedPath(t, realHome)
	wantSource := fsPath(t, filepath.Join(canonicalHome, "repo", "missing", "source"))
	if roots.Source != wantSource {
		t.Fatalf("source = %q, want %q", roots.Source, wantSource)
	}
	if roots.Targets[domain.RootHome] != fsPath(t, canonicalHome) {
		t.Fatalf("home = %q", roots.Targets[domain.RootHome])
	}
	if roots.Targets[domain.RootClaudeConfig] != fsPath(t, filepath.Join(canonicalHome, ".claude")) {
		t.Fatalf("claude = %q", roots.Targets[domain.RootClaudeConfig])
	}
	if _, err := fs.Stat(namespace.Filesystem(), string(roots.Targets[domain.RootHome])); err != nil {
		t.Fatalf("Filesystem() cannot stat canonical home: %v", err)
	}

	roots.Targets[domain.RootHome] = "mutated"
	delete(roots.Targets, domain.RootCodexConfig)
	again := namespace.Roots()
	if again.Targets[domain.RootHome] != fsPath(t, canonicalHome) {
		t.Fatal("Roots() exposed mutable target storage")
	}
	if _, exists := again.Targets[domain.RootCodexConfig]; !exists {
		t.Fatal("Roots() mutation deleted internal target")
	}
}

func TestOpenResolvesRelativeAndAbsoluteSymlinkAncestors(t *testing.T) {
	base := t.TempDir()
	realHome := filepath.Join(base, "real", "home")
	mustMkdirAll(t, realHome)
	mustMkdirAll(t, filepath.Join(base, "aliases"))
	relativeAlias := filepath.Join(base, "aliases", "relative")
	relativeTarget, err := filepath.Rel(filepath.Dir(relativeAlias), realHome)
	if err != nil {
		t.Fatal(err)
	}
	mustSymlink(t, relativeTarget, relativeAlias)
	absoluteAlias := filepath.Join(base, "absolute")
	mustSymlink(t, realHome, absoluteAlias)
	layout := mustLayout(t, relativeAlias, filepath.Join(absoluteAlias, "repo"), map[string]string{
		"CODEX_HOME": filepath.Join(absoluteAlias, ".claude"),
	})

	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	roots := namespace.Roots()
	if roots.Targets[domain.RootClaudeConfig] != roots.Targets[domain.RootCodexConfig] {
		t.Fatalf("aliased roots differ: claude=%q codex=%q", roots.Targets[domain.RootClaudeConfig], roots.Targets[domain.RootCodexConfig])
	}
	if roots.Source != fsPath(t, filepath.Join(evaluatedPath(t, realHome), "repo")) {
		t.Fatalf("source = %q", roots.Source)
	}
}

func TestCanonicalRootsExposePhysicalArtifactCollisions(t *testing.T) {
	base := t.TempDir()
	realHome := filepath.Join(base, "real-home")
	realConfig := filepath.Join(realHome, ".claude")
	mustMkdirAll(t, realConfig)
	homeAlias := filepath.Join(base, "home")
	codexAlias := filepath.Join(base, "codex")
	mustSymlink(t, realHome, homeAlias)
	mustSymlink(t, realConfig, codexAlias)
	layout := mustLayout(t, homeAlias, filepath.Join(base, "source"), map[string]string{"CODEX_HOME": codexAlias})
	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: "claude", Artifacts: []installmodel.ArtifactSpec{{Target: domain.Location{Root: domain.RootClaudeConfig, Path: "AGENTS.md"}, SourcePath: "dist/claude"}}},
		{ID: "codex", Artifacts: []installmodel.ArtifactSpec{{Target: domain.Location{Root: domain.RootCodexConfig, Path: "AGENTS.md"}, SourcePath: "dist/codex"}}},
	})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	_, err = discovery.Discover(model, namespace.Filesystem(), namespace.Roots())
	if err == nil || !strings.Contains(err.Error(), "collide") {
		t.Fatalf("Discover() error = %v, want collision", err)
	}
}

func TestOpenRejectsUnsafeFilesystemLayouts(t *testing.T) {
	t.Run("dangling symlink", func(t *testing.T) {
		base := t.TempDir()
		dangling := filepath.Join(base, "dangling")
		mustSymlink(t, filepath.Join(base, "missing"), dangling)
		layout := mustLayout(t, dangling, filepath.Join(base, "source"), nil)
		assertOpenError(t, layout, "symlink")
	})

	t.Run("symlink cycle", func(t *testing.T) {
		base := t.TempDir()
		first := filepath.Join(base, "first")
		second := filepath.Join(base, "second")
		mustSymlink(t, second, first)
		mustSymlink(t, first, second)
		layout := mustLayout(t, first, filepath.Join(base, "source"), nil)
		assertOpenError(t, layout, "symlink")
	})

	t.Run("file ancestor", func(t *testing.T) {
		base := t.TempDir()
		file := filepath.Join(base, "file")
		if err := os.WriteFile(file, []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
		layout := mustLayout(t, filepath.Join(file, "home"), filepath.Join(base, "source"), nil)
		assertOpenError(t, layout, "not a directory")
	})

	t.Run("file source", func(t *testing.T) {
		base := t.TempDir()
		file := filepath.Join(base, "source")
		if err := os.WriteFile(file, []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
		layout := mustLayout(t, filepath.Join(base, "home"), file, nil)
		assertOpenError(t, layout, "not a directory")
	})

	t.Run("permission denied ancestor", func(t *testing.T) {
		base := t.TempDir()
		blocked := filepath.Join(base, "blocked")
		mustMkdirAll(t, blocked)
		if err := os.Chmod(blocked, 0); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = os.Chmod(blocked, 0o700) })
		layout := mustLayout(t, filepath.Join(blocked, "home"), filepath.Join(base, "source"), nil)
		_, err := hostfs.Open(layout)
		if os.Geteuid() != 0 && (err == nil || !errors.Is(err, fs.ErrPermission)) {
			t.Fatalf("Open() error = %v, want permission error", err)
		}
	})
}

func mustLayout(t *testing.T, home, source string, extra map[string]string) hostlayout.Layout {
	t.Helper()
	values := map[string]string{"HOME": home}
	for key, value := range extra {
		values[key] = value
	}
	layout, err := hostlayout.Resolve(hostlayout.Environment{
		LookupEnv: func(key string) (string, bool) {
			value, exists := values[key]
			return value, exists
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "linux",
	}, source)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	return layout
}

func assertOpenError(t *testing.T, layout hostlayout.Layout, contains string) {
	t.Helper()
	_, err := hostfs.Open(layout)
	if err == nil || !strings.Contains(err.Error(), contains) {
		t.Fatalf("Open() error = %v, want containing %q", err, contains)
	}
}

func mustMkdirAll(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(path, 0o700); err != nil {
		t.Fatal(err)
	}
}

func mustSymlink(t *testing.T, target, link string) {
	t.Helper()
	if err := os.Symlink(target, link); err != nil {
		t.Fatal(err)
	}
}

func fsPath(t *testing.T, absolute string) domain.ArtifactPath {
	t.Helper()
	clean := filepath.Clean(absolute)
	relative := strings.TrimPrefix(filepath.ToSlash(clean), "/")
	if relative == "" {
		t.Fatal("test path resolves to filesystem root")
	}
	return domain.ArtifactPath(relative)
}

func evaluatedPath(t *testing.T, path string) string {
	t.Helper()
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		t.Fatal(err)
	}
	return resolved
}
