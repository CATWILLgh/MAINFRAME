//go:build darwin || linux

package releasecache

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestImportPublishesValidatedVersionAndPreservesPayloadMode(t *testing.T) {
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
	if info.Mode().Perm() != 0o640 {
		t.Fatalf("stored payload mode = %#o, want 0640", info.Mode().Perm())
	}
}

func TestInspectImportPredictsExactDestinationWithoutWriting(t *testing.T) {
	parent := canonicalTempDir(t)
	root := filepath.Join(parent, "mainframe")
	store, err := New(root)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	source := writeReleaseFixture(
		t,
		"test-release",
		"payload\n",
		0o640,
	)

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
	source := writeReleaseFixture(
		t,
		"test-release",
		"payload\n",
		0o640,
	)
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
	if err := os.WriteFile(
		filepath.Join(imported.Path, "bundles", "codex", "payload.txt"),
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
	if err := os.WriteFile(
		filepath.Join(entry.Path, "bundles", "codex", "payload.txt"),
		[]byte("tampered\n"),
		0o640,
	); err != nil {
		t.Fatalf("tamper stored payload: %v", err)
	}

	if _, err := store.Import(source); err == nil || !strings.Contains(err.Error(), "existing release") {
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

	if _, err := store.Import(accepted); err == nil || !strings.Contains(err.Error(), "source changed") {
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
		if err := os.WriteFile(filepath.Join(destination, "partial"), []byte("x"), 0o600); err != nil {
			return err
		}
		return errors.New("injected copy failure")
	}

	if _, err := store.Import(source); err == nil || !strings.Contains(err.Error(), "injected copy failure") {
		t.Fatalf("copy failure error = %v", err)
	}
	assertNoPublishedOrStagedVersion(t, store.root)
}

func TestConcurrentImportPublishesOneCompleteVersion(t *testing.T) {
	source := writeReleaseFixture(t, "test-release", "payload\n", 0o640)
	store := newTestStore(t)
	const workers = 8
	results := make([]Entry, workers)
	errorsSeen := make([]error, workers)
	var wait sync.WaitGroup
	wait.Add(workers)
	for index := 0; index < workers; index++ {
		go func() {
			defer wait.Done()
			results[index], errorsSeen[index] = store.Import(source)
		}()
	}
	wait.Wait()

	newCount := 0
	for index, err := range errorsSeen {
		if err != nil {
			t.Fatalf("Import() worker %d error = %v", index, err)
		}
		if !results[index].AlreadyPresent {
			newCount++
		}
		if results[index].Path != results[0].Path {
			t.Fatalf("worker %d path = %q, want %q", index, results[index].Path, results[0].Path)
		}
	}
	if newCount != 1 {
		t.Fatalf("new publication count = %d, want 1", newCount)
	}
	if _, err := releasecontract.Load(results[0].Path); err != nil {
		t.Fatalf("load concurrently published release: %v", err)
	}
}

func TestNewRejectsInvalidRoot(t *testing.T) {
	unclean := t.TempDir() + string(filepath.Separator) + "parent" +
		string(filepath.Separator) + ".." + string(filepath.Separator) + "root"
	for _, root := range []string{
		"relative",
		unclean,
		"bad\x00root",
		string(filepath.Separator),
		filepath.Join(t.TempDir(), "other-product"),
	} {
		t.Run(strings.ReplaceAll(root, string(filepath.Separator), "_"), func(t *testing.T) {
			if _, err := New(root); err == nil {
				t.Fatalf("New(%q) succeeded", root)
			}
		})
	}
}

func TestZeroStoreFailsClosed(t *testing.T) {
	if _, err := (Store{}).Import(writeReleaseFixture(t, "test-release", "payload\n", 0o640)); err == nil {
		t.Fatal("zero Store.Import() succeeded")
	}
}

func TestImportPinsAnExistingSymlinkAncestorAtInitialization(t *testing.T) {
	first := canonicalTempDir(t)
	second := canonicalTempDir(t)
	container := canonicalTempDir(t)
	link := filepath.Join(container, "data")
	if err := os.Symlink(first, link); err != nil {
		t.Fatalf("create data symlink: %v", err)
	}
	store, err := New(filepath.Join(link, "mainframe"))
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	if err := os.Remove(link); err != nil {
		t.Fatalf("remove data symlink: %v", err)
	}
	if err := os.Symlink(second, link); err != nil {
		t.Fatalf("retarget data symlink: %v", err)
	}

	entry, err := store.Import(writeReleaseFixture(t, "test-release", "payload\n", 0o640))
	if err != nil {
		t.Fatalf("Import() error = %v", err)
	}
	if !strings.HasPrefix(entry.Path, filepath.Join(first, "mainframe")+string(filepath.Separator)) {
		t.Fatalf("published path = %q, want below %q", entry.Path, first)
	}
	if _, err := os.Lstat(filepath.Join(second, "mainframe")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("retargeted ancestor received store content: %v", err)
	}
}

func TestImportRejectsSymlinkInsertedAfterInitialization(t *testing.T) {
	container := canonicalTempDir(t)
	outside := canonicalTempDir(t)
	store, err := New(filepath.Join(container, "mainframe"))
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	if err := os.Symlink(outside, filepath.Join(container, "mainframe")); err != nil {
		t.Fatalf("insert store symlink: %v", err)
	}

	if _, err := store.Import(writeReleaseFixture(t, "test-release", "payload\n", 0o640)); err == nil {
		t.Fatal("Import() accepted a substituted store symlink")
	}
	if _, err := os.Lstat(filepath.Join(outside, "releases")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("substituted store received content: %v", err)
	}
}

func newTestStore(t *testing.T) Store {
	t.Helper()
	store, err := New(filepath.Join(canonicalTempDir(t), "mainframe"))
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	return store
}

func canonicalTempDir(t *testing.T) string {
	t.Helper()
	path, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("resolve temporary directory: %v", err)
	}
	return path
}

func assertNoPublishedOrStagedVersion(t *testing.T, root string) {
	t.Helper()
	entries, err := filepath.Glob(filepath.Join(root, "releases", "test-release", "*"))
	if err != nil {
		t.Fatalf("glob release versions: %v", err)
	}
	if len(entries) != 0 {
		t.Fatalf("release directory contains %v", entries)
	}
}

func firstSourceCopy(t *testing.T, source string) string {
	t.Helper()
	destination := filepath.Join(t.TempDir(), "release")
	if err := copyTree(source, destination); err != nil {
		t.Fatalf("copy stored release: %v", err)
	}
	return destination
}

func writeReleaseFixture(
	t *testing.T,
	releaseID string,
	payload string,
	mode os.FileMode,
) string {
	t.Helper()
	root := t.TempDir()
	bundle := filepath.Join(root, "bundles", "codex")
	if err := os.MkdirAll(bundle, 0o755); err != nil {
		t.Fatalf("mkdir fixture bundle: %v", err)
	}
	payloadPath := filepath.Join(bundle, "payload.txt")
	if err := os.WriteFile(payloadPath, []byte(payload), mode); err != nil {
		t.Fatalf("write fixture payload: %v", err)
	}
	manifestPath := filepath.Join(bundle, "bundle.json")
	writeFixtureJSON(t, manifestPath, fixtureManifest(t, payloadPath, mode))
	catalogPayload, err := os.ReadFile(filepath.Join("..", "mcpcatalog", "catalog.json"))
	if err != nil {
		t.Fatalf("read fixture MCP catalog: %v", err)
	}
	metadata := filepath.Join(root, "metadata")
	if err := os.MkdirAll(metadata, 0o755); err != nil {
		t.Fatalf("mkdir fixture metadata: %v", err)
	}
	catalogPath := filepath.Join(metadata, "mcp-catalog.json")
	if err := os.WriteFile(catalogPath, catalogPayload, 0o644); err != nil {
		t.Fatalf("write fixture MCP catalog: %v", err)
	}
	writeFixtureJSON(t, filepath.Join(root, "release.json"), map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-release",
		"release_id":     releaseID,
		"mcp_catalog": map[string]any{
			"path": "metadata/mcp-catalog.json", "sha256": fileDigest(t, catalogPath),
		},
		"manifests": []any{map[string]any{
			"component": "codex",
			"path":      "bundles/codex/bundle.json",
			"sha256":    fileDigest(t, manifestPath),
		}},
	})
	return root
}

func fixtureManifest(t *testing.T, payloadPath string, mode os.FileMode) map[string]any {
	t.Helper()
	info, err := os.Stat(payloadPath)
	if err != nil {
		t.Fatalf("stat fixture payload: %v", err)
	}
	return map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-bundle",
		"component":      "codex",
		"dependencies":   []string{},
		"install_units": []any{map[string]any{
			"id": "codex.payload", "kind": "file", "source": "payload.txt",
			"target": map[string]any{"root": "codex-config", "path": "payload.txt"},
		}},
		"legacy_artifacts": []any{},
		"resources":        []any{},
		"payload_files": []any{map[string]any{
			"path": "payload.txt", "mode": formatMode(mode),
			"size": info.Size(), "sha256": fileDigest(t, payloadPath),
		}},
		"runtime_profile": map[string]string{"config_root": "${CODEX_HOME}"},
		"mcp_projections": []any{},
	}
}

func writeFixtureJSON(t *testing.T, path string, value any) {
	t.Helper()
	payload, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("encode fixture %s: %v", path, err)
	}
	payload = append(payload, '\n')
	if err := os.WriteFile(path, payload, 0o644); err != nil {
		t.Fatalf("write fixture %s: %v", path, err)
	}
}

func fileDigest(t *testing.T, path string) string {
	t.Helper()
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read fixture %s: %v", path, err)
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func formatMode(mode os.FileMode) string {
	return fmt.Sprintf("%04o", mode.Perm())
}
