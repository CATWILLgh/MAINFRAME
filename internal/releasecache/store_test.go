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
	t.Cleanup(func() {
		_ = filepath.WalkDir(path, func(current string, entry os.DirEntry, err error) error {
			if err != nil || !entry.IsDir() {
				return nil
			}
			_ = os.Chmod(current, 0o700)
			return nil
		})
	})
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

func assertSealedTree(t *testing.T, root string) {
	t.Helper()
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if info.Mode().Perm()&0o222 != 0 {
			return fmt.Errorf("%q has writable mode %#o", path, info.Mode().Perm())
		}
		return nil
	})
	if err != nil {
		t.Fatalf("cached release is not sealed: %v", err)
	}
}

func firstSourceCopy(t *testing.T, source string) string {
	t.Helper()
	parent := t.TempDir()
	t.Cleanup(func() {
		makeFixtureTreeRemovable(parent)
	})
	destination := filepath.Join(parent, "release")
	if err := copyTree(source, destination); err != nil {
		t.Fatalf("copy stored release: %v", err)
	}
	if err := os.Chmod(destination, 0o555); err != nil {
		t.Fatalf("seal copied release root: %v", err)
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
	t.Cleanup(func() {
		makeFixtureTreeRemovable(root)
	})
	bundle := filepath.Join(root, "bundles", "codex")
	if err := os.MkdirAll(bundle, 0o755); err != nil {
		t.Fatalf("mkdir fixture bundle: %v", err)
	}
	payloadPath := filepath.Join(bundle, "payload.txt")
	sealedMode := mode &^ 0o222
	if err := os.WriteFile(payloadPath, []byte(payload), sealedMode); err != nil {
		t.Fatalf("write fixture payload: %v", err)
	}
	manifestPath := filepath.Join(bundle, "bundle.json")
	writeFixtureJSON(t, manifestPath, fixtureManifest(t, payloadPath, sealedMode))
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
	sealFixtureTree(t, root)
	return root
}

func sealFixtureTree(t *testing.T, root string) {
	t.Helper()
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		return os.Chmod(path, info.Mode().Perm()&^0o222)
	})
	if err != nil {
		t.Fatalf("seal fixture files: %v", err)
	}
}

func makeFixtureTreeRemovable(root string) {
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			_ = os.Chmod(path, 0o700)
		}
		return nil
	})
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

func TestListReturnsEmptyForUninitializedCache(t *testing.T) {
	store := newTestStore(t)
	entries, err := store.List()
	if err != nil {
		t.Fatalf("List() on empty store error = %v", err)
	}
	if len(entries) != 0 {
		t.Fatalf("List() empty store = %v entries, want 0", len(entries))
	}
}

func TestListReturnsImportedReleasesWithIdentity(t *testing.T) {
	store := newTestStore(t)
	first := writeReleaseFixture(t, "alpha-release", "first\n", 0o640)
	second := writeReleaseFixture(t, "beta-release", "second\n", 0o640)
	if _, err := store.Import(first); err != nil {
		t.Fatalf("Import first: %v", err)
	}
	if _, err := store.Import(second); err != nil {
		t.Fatalf("Import second: %v", err)
	}

	entries, err := store.List()
	if err != nil {
		t.Fatalf("List() error = %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("List() = %v entries, want 2", len(entries))
	}
	byID := map[string]Entry{}
	for _, entry := range entries {
		byID[entry.ReleaseID] = entry
		if entry.AlreadyPresent {
			t.Fatalf("List() entry %+v reports AlreadyPresent, must be false for listing", entry)
		}
	}
	for _, want := range []string{"alpha-release", "beta-release"} {
		entry, ok := byID[want]
		if !ok {
			t.Fatalf("List() missing release %q in %v", want, entries)
		}
		if entry.IndexSHA256 == "" {
			t.Fatalf("List() entry for %q has empty IndexSHA256", want)
		}
		if !releasecontract.ValidReleaseIdentity(entry.ReleaseID, entry.IndexSHA256) {
			t.Fatalf("List() entry for %q has invalid identity", want)
		}
		if _, err := releasecontract.Load(entry.Path); err != nil {
			t.Fatalf("List() entry for %q not loadable: %v", want, err)
		}
	}
}

func TestListSkipsIncompletePublication(t *testing.T) {
	store := newTestStore(t)
	source := writeReleaseFixture(t, "good-release", "payload\n", 0o640)
	if _, err := store.Import(source); err != nil {
		t.Fatalf("Import good release: %v", err)
	}
	releasesRoot := filepath.Join(store.root, releasesDirectory)
	brokenID := "broken-release"
	brokenVersion := strings.Repeat("a", sha256.Size*2)
	brokenPath := filepath.Join(releasesRoot, brokenID, brokenVersion)
	if err := os.MkdirAll(brokenPath, 0o700); err != nil {
		t.Fatalf("mkdir broken release dir: %v", err)
	}

	entries, err := store.List()
	if err != nil {
		t.Fatalf("List() with broken sibling error = %v", err)
	}
	for _, entry := range entries {
		if entry.ReleaseID == brokenID {
			t.Fatalf("List() surfaced incomplete publication %+v", entry)
		}
	}
	if len(entries) != 1 {
		t.Fatalf("List() = %v entries, want 1 (good only); entries=%+v", len(entries), entries)
	}
	if entries[0].ReleaseID != "good-release" {
		t.Fatalf("List()[0].ReleaseID = %q, want good-release", entries[0].ReleaseID)
	}
}
