package hostfs_test

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestInspectDigestReturnsIdentityAndDigestWithoutContent(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	mustMkdirAll(t, home)
	const value = "private-value"
	writeHostFile(t, filepath.Join(home, "credential"), value)
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	entry, err := namespace.InspectDigest(
		domain.Location{Root: domain.RootHome, Path: "credential"},
	)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(value))
	if entry.Kind != hostfs.EntryRegular ||
		entry.SHA256 != hex.EncodeToString(sum[:]) ||
		entry.Content != nil ||
		entry.Device == 0 ||
		entry.Inode == 0 {
		t.Fatalf("digest-only entry = %#v", entry)
	}
}

func TestInspectReadsRegularFileWithoutFollowingFinalSymlink(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	mustMkdirAll(t, home)
	writeHostFile(t, filepath.Join(home, ".zshenv"), "source ~/.config/mainframe/env\n")
	writeHostFile(t, filepath.Join(home, "outside"), "private\n")
	mustSymlink(t, filepath.Join(home, "outside"), filepath.Join(home, "linked"))
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	entry, err := namespace.Inspect(domain.Location{Root: domain.RootHome, Path: ".zshenv"}, true)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	if entry.Kind != hostfs.EntryRegular || string(entry.Content) != "source ~/.config/mainframe/env\n" {
		t.Fatalf("entry = %#v", entry)
	}

	entry, err = namespace.Inspect(domain.Location{Root: domain.RootHome, Path: "linked"}, true)
	if err != nil {
		t.Fatalf("Inspect(symlink) error = %v", err)
	}
	if entry.Kind != hostfs.EntrySymlink || entry.Content != nil {
		t.Fatalf("symlink entry = %#v", entry)
	}
}

func TestInspectCapturesFinalSymlinkTargetWithoutFollowingIt(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	config := filepath.Join(home, ".gemini", "config")
	legacy := filepath.Join(home, ".gemini", "antigravity")
	mustMkdirAll(t, config)
	mustMkdirAll(t, legacy)
	target := filepath.Join(config, "mcp_config.json")
	writeHostFile(t, target, "{}\n")
	canonicalTarget, err := filepath.EvalSymlinks(target)
	if err != nil {
		t.Fatal(err)
	}
	canonicalLegacy, err := filepath.EvalSymlinks(legacy)
	if err != nil {
		t.Fatal(err)
	}
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	for _, test := range []struct {
		name   string
		target string
	}{
		{name: "absolute", target: canonicalTarget},
		{name: "relative", target: "../config/mcp_config.json"},
	} {
		t.Run(test.name, func(t *testing.T) {
			link := filepath.Join(legacy, test.name)
			mustSymlink(t, test.target, link)
			entry, err := namespace.Inspect(
				domain.Location{
					Root: domain.RootHome,
					Path: domain.ArtifactPath(
						filepath.Join(".gemini", "antigravity", test.name),
					),
				},
				true,
			)
			if err != nil {
				t.Fatalf("Inspect() error = %v", err)
			}
			if entry.Kind != hostfs.EntrySymlink ||
				entry.Path != filepath.Join(canonicalLegacy, test.name) ||
				entry.SymlinkTargetPath != canonicalTarget ||
				entry.Content != nil {
				t.Fatalf("symlink entry = %#v", entry)
			}
		})
	}
}

func TestInspectRejectsSymlinkedAncestorAndInvalidLocation(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	outside := filepath.Join(base, "outside")
	mustMkdirAll(t, home)
	mustMkdirAll(t, outside)
	writeHostFile(t, filepath.Join(outside, "value"), "private\n")
	mustSymlink(t, outside, filepath.Join(home, "linked-dir"))
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	_, err := namespace.Inspect(domain.Location{Root: domain.RootHome, Path: "linked-dir/value"}, true)
	if err == nil || !strings.Contains(err.Error(), "symbolic link") {
		t.Fatalf("Inspect(symlink ancestor) error = %v", err)
	}
	_, err = namespace.Inspect(domain.Location{Root: "unknown", Path: "value"}, false)
	if err == nil || !strings.Contains(err.Error(), "unknown root") {
		t.Fatalf("Inspect(unknown root) error = %v", err)
	}
	_, err = namespace.Inspect(domain.Location{Root: domain.RootHome, Path: "../value"}, false)
	if err == nil || !strings.Contains(err.Error(), "invalid") {
		t.Fatalf("Inspect(invalid path) error = %v", err)
	}
}

func TestInspectReportsMissingTarget(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	mustMkdirAll(t, home)
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	_, err := namespace.Inspect(domain.Location{Root: domain.RootHome, Path: "missing/child"}, false)
	if !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("Inspect(missing) error = %v", err)
	}
}

func TestInspectLimitsConfigurationContent(t *testing.T) {
	base := t.TempDir()
	home := filepath.Join(base, "home")
	mustMkdirAll(t, home)
	if err := os.WriteFile(filepath.Join(home, ".zshenv"), make([]byte, (1<<20)+1), 0o600); err != nil {
		t.Fatal(err)
	}
	namespace := openTestNamespace(t, home, filepath.Join(base, "release"))

	_, err := namespace.Inspect(domain.Location{Root: domain.RootHome, Path: ".zshenv"}, true)
	if err == nil || !strings.Contains(err.Error(), "size limit") {
		t.Fatalf("Inspect(oversized) error = %v", err)
	}
}

func openTestNamespace(t *testing.T, home, source string) hostfs.Namespace {
	t.Helper()
	layout := mustLayout(t, home, source, nil)
	namespace, err := hostfs.Open(layout)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	return namespace
}

func writeHostFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}
