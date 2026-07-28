//go:build darwin || linux

package releasecache

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestImportPublishesValidatedSealedVersion(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "first\n", 0o640)
	store := newTestStore(t)

	entry, err := store.Import(source)
	if err != nil {
		t.Fatalf("Import() error = %v", err)
	}
	if entry.AlreadyPresent {
		t.Fatal("first import reported an existing release")
	}
	loaded, err := releasecontract.Load(entry.Path)
	if err != nil {
		t.Fatalf("load stored release: %v", err)
	}
	if loaded.ID != entry.ReleaseID || loaded.IndexSHA256 != entry.IndexSHA256 {
		t.Fatalf("stored identity = (%q, %q), entry = (%q, %q)",
			loaded.ID, loaded.IndexSHA256, entry.ReleaseID, entry.IndexSHA256)
	}
	info, err := os.Stat(filepath.Join(entry.Path, "bundles", "codex", "payload.txt"))
	if err != nil {
		t.Fatalf("stat stored payload: %v", err)
	}
	if info.Mode().Perm() != 0o440 {
		t.Fatalf("stored payload mode = %#o, want 0440", info.Mode().Perm())
	}
	assertSealedTree(t, entry.Path)
}

func TestImportCleansPublishedVersionWhenRootSealingFails(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "first\n", 0o640)
	store := newTestStore(t)
	expected, err := store.InspectImport(source)
	if err != nil {
		t.Fatalf("InspectImport() error = %v", err)
	}
	store.sealRoot = func(string) error {
		return errors.New("injected root seal failure")
	}

	_, err = store.Import(source)
	if err == nil || !strings.Contains(err.Error(), "injected root seal failure") {
		t.Fatalf("Import() error = %v", err)
	}
	if _, statErr := os.Lstat(expected.Path); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("failed publication survived at %q: %v", expected.Path, statErr)
	}
}

func TestImportCleansVersionWhenPublicationSyncFails(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "first\n", 0o640)
	store := newTestStore(t)
	expected, err := store.InspectImport(source)
	if err != nil {
		t.Fatalf("InspectImport() error = %v", err)
	}
	store.publish = func(parent, staging, destination string) (bool, error) {
		published, err := publishNoReplace(parent, staging, destination)
		if err != nil {
			return published, err
		}
		return true, errors.New("injected publication sync failure")
	}

	_, err = store.Import(source)
	if err == nil || !strings.Contains(err.Error(), "injected publication sync failure") {
		t.Fatalf("Import() error = %v", err)
	}
	if _, statErr := os.Lstat(expected.Path); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("failed publication survived at %q: %v", expected.Path, statErr)
	}
}

func TestImportRecoversValidPublicationInterruptedBeforeRootSeal(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "first\n", 0o640)
	store := newTestStore(t)
	expected, err := store.InspectImport(source)
	if err != nil {
		t.Fatalf("InspectImport() error = %v", err)
	}
	versionParent, err := store.prepare(expected.ReleaseID)
	if err != nil {
		t.Fatalf("prepare version parent: %v", err)
	}
	staging, err := os.MkdirTemp(versionParent, stagingPrefix)
	if err != nil {
		t.Fatalf("create interrupted staging: %v", err)
	}
	if err := copyTree(source, staging); err != nil {
		t.Fatalf("copy interrupted publication: %v", err)
	}
	if err := sealStagedDirectories(staging); err != nil {
		t.Fatalf("seal interrupted publication: %v", err)
	}
	published, err := publishNoReplace(
		versionParent,
		filepath.Base(staging),
		expected.IndexSHA256,
	)
	if err != nil || !published {
		t.Fatalf("publish interrupted version = %v, %v", published, err)
	}

	entry, err := store.Import(source)
	if err != nil {
		t.Fatalf("Import() recovery error = %v", err)
	}
	if !entry.AlreadyPresent {
		t.Fatal("recovered publication was not reported as existing")
	}
	assertSealedTree(t, entry.Path)
}

func TestImportRejectsWritableReleaseMetadata(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "first\n", 0o640)
	if err := os.Chmod(filepath.Join(source, "release.json"), 0o644); err != nil {
		t.Fatalf("make release index writable: %v", err)
	}

	if _, err := newTestStore(t).Import(source); err == nil ||
		!strings.Contains(err.Error(), "not sealed") {
		t.Fatalf("Import() error = %v, want sealed-release rejection", err)
	}
}

func TestInspectImportPredictsExactDestinationWithoutWriting(t *testing.T) {
	parent := canonicalTempDir(t)
	root := filepath.Join(parent, "mainframe")
	store, err := New(root)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	source := writeReleaseFixture(t, "test-release", "payload\n", 0o640)

	entry, err := store.InspectImport(source)
	if err != nil {
		t.Fatalf("InspectImport() error = %v", err)
	}
	if entry.AlreadyPresent ||
		entry.Path != filepath.Join(
			root,
			"releases",
			entry.ReleaseID,
			entry.IndexSHA256,
		) {
		t.Fatalf("InspectImport() = %#v", entry)
	}
	if _, statErr := os.Lstat(root); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("InspectImport() created release store: %v", statErr)
	}
}

func TestInspectImportReportsAnExistingExactVersion(t *testing.T) {
	store := newTestStore(t)
	source := writeReleaseFixture(t, "test-release", "payload\n", 0o640)
	imported, err := store.Import(source)
	if err != nil {
		t.Fatalf("Import() error = %v", err)
	}

	inspected, err := store.InspectImport(source)
	if err != nil {
		t.Fatalf("InspectImport() error = %v", err)
	}
	if !inspected.AlreadyPresent ||
		inspected.Path != imported.Path ||
		inspected.ReleaseID != imported.ReleaseID ||
		inspected.IndexSHA256 != imported.IndexSHA256 {
		t.Fatalf("InspectImport() = %#v, imported = %#v", inspected, imported)
	}
}

func TestImportIsIdempotentAndRetainsDistinctVersions(t *testing.T) {
	store := newTestStore(t)
	first, err := store.Import(writeReleaseFixture(t, "test-release", "first\n", 0o640))
	if err != nil {
		t.Fatalf("first Import() error = %v", err)
	}
	repeated, err := store.Import(firstSourceCopy(t, first.Path))
	if err != nil {
		t.Fatalf("repeated Import() error = %v", err)
	}
	if !repeated.AlreadyPresent || repeated.Path != first.Path {
		t.Fatalf("repeated import = %#v, want existing %q", repeated, first.Path)
	}

	second, err := store.Import(writeReleaseFixture(t, "test-release", "second\n", 0o640))
	if err != nil {
		t.Fatalf("second version Import() error = %v", err)
	}
	if second.Path == first.Path || second.AlreadyPresent {
		t.Fatalf("second version = %#v, first = %#v", second, first)
	}
	if _, err := releasecontract.Load(first.Path); err != nil {
		t.Fatalf("first version was not retained: %v", err)
	}
}
