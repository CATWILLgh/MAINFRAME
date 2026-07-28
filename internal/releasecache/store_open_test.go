//go:build darwin || linux

package releasecache

import (
	"crypto/sha256"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestOpenReturnsOnlyTheExactValidatedVersion(t *testing.T) {
	store := newTestStore(t)
	imported, err := store.Import(
		writeReleaseFixture(t, "test-release", "payload\n", 0o640),
	)
	if err != nil {
		t.Fatalf("Import() error = %v", err)
	}

	opened, err := store.Open(imported.ReleaseID, imported.IndexSHA256)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	if opened.Path != imported.Path ||
		opened.ReleaseID != imported.ReleaseID ||
		opened.IndexSHA256 != imported.IndexSHA256 ||
		!opened.AlreadyPresent {
		t.Fatalf("Open() = %#v, imported = %#v", opened, imported)
	}
}

func TestOpenMissingVersionIsReadOnly(t *testing.T) {
	parent := canonicalTempDir(t)
	root := filepath.Join(parent, "mainframe")
	store, err := New(root)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	_, err = store.Open(
		"missing-release",
		strings.Repeat("a", sha256.Size*2),
	)
	if err == nil || !strings.Contains(err.Error(), "not found") {
		t.Fatalf("Open() error = %v, want not found", err)
	}
	if _, statErr := os.Lstat(root); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("Open() created release store: %v", statErr)
	}
}

func TestOpenRejectsMalformedIdentity(t *testing.T) {
	store := newTestStore(t)
	tests := []struct {
		releaseID string
		digest    string
	}{
		{"../escape", strings.Repeat("a", sha256.Size*2)},
		{"test-release", "../escape"},
		{"test-release", strings.Repeat("A", sha256.Size*2)},
	}
	for _, test := range tests {
		if _, err := store.Open(test.releaseID, test.digest); err == nil {
			t.Fatalf(
				"Open(%q, %q) accepted malformed identity",
				test.releaseID,
				test.digest,
			)
		}
	}
}

func TestOpenRejectsTamperedStoredVersion(t *testing.T) {
	store := newTestStore(t)
	imported, err := store.Import(
		writeReleaseFixture(t, "test-release", "payload\n", 0o640),
	)
	if err != nil {
		t.Fatalf("Import() error = %v", err)
	}
	payloadPath := filepath.Join(imported.Path, "bundles", "codex", "payload.txt")
	if err := os.Chmod(payloadPath, 0o640); err != nil {
		t.Fatalf("make stored payload writable: %v", err)
	}
	if err := os.WriteFile(
		payloadPath,
		[]byte("tampered\n"),
		0o640,
	); err != nil {
		t.Fatalf("tamper stored payload: %v", err)
	}

	if _, err := store.Open(
		imported.ReleaseID,
		imported.IndexSHA256,
	); err == nil {
		t.Fatal("Open() accepted a tampered stored release")
	}
}

func TestOpenRejectsStoreSymlinkInsertedAfterInitialization(t *testing.T) {
	container := canonicalTempDir(t)
	root := filepath.Join(container, "mainframe")
	store, err := New(root)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	outside := newTestStore(t)
	imported, err := outside.Import(
		writeReleaseFixture(t, "test-release", "payload\n", 0o640),
	)
	if err != nil {
		t.Fatalf("outside Import() error = %v", err)
	}
	if err := os.Symlink(outside.root, root); err != nil {
		t.Fatalf("insert store symlink: %v", err)
	}

	if _, err := store.Open(
		imported.ReleaseID,
		imported.IndexSHA256,
	); err == nil {
		t.Fatal("Open() accepted a substituted store symlink")
	}
}

func TestImportRejectsTamperedExistingVersion(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "payload\n", 0o640)
	store := newTestStore(t)
	entry, err := store.Import(source)
	if err != nil {
		t.Fatalf("initial Import() error = %v", err)
	}
	payloadPath := filepath.Join(entry.Path, "bundles", "codex", "payload.txt")
	if err := os.Chmod(payloadPath, 0o640); err != nil {
		t.Fatalf("make stored payload writable: %v", err)
	}
	if err := os.WriteFile(
		payloadPath,
		[]byte("tampered\n"),
		0o640,
	); err != nil {
		t.Fatalf("tamper stored payload: %v", err)
	}

	if _, err := store.Import(source); err == nil ||
		!strings.Contains(err.Error(), "existing release") {
		t.Fatalf("tampered existing release error = %v", err)
	}
}

func TestImportRejectsChangedSnapshotAndCleansStaging(t *testing.T) {
	accepted := writeReleaseFixture(t, "test-release", "accepted\n", 0o640)
	changed := writeReleaseFixture(t, "test-release", "changed\n", 0o640)
	store := newTestStore(t)
	store.copyTree = func(_ string, destination string) error {
		return copyTree(changed, destination)
	}

	if _, err := store.Import(accepted); err == nil ||
		!strings.Contains(err.Error(), "source changed") {
		t.Fatalf("changed snapshot error = %v", err)
	}
	assertNoPublishedOrStagedVersion(t, store.root)
}

func TestImportFailureLeavesNoPublishedOrStagedVersion(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "payload\n", 0o640)
	store := newTestStore(t)
	store.copyTree = func(_ string, destination string) error {
		if err := os.MkdirAll(destination, 0o700); err != nil {
			return err
		}
		if err := os.WriteFile(
			filepath.Join(destination, "partial"),
			[]byte("x"),
			0o600,
		); err != nil {
			return err
		}
		return errors.New("injected copy failure")
	}

	if _, err := store.Import(source); err == nil ||
		!strings.Contains(err.Error(), "injected copy failure") {
		t.Fatalf("copy failure error = %v", err)
	}
	assertNoPublishedOrStagedVersion(t, store.root)
}
