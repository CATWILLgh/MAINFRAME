//go:build darwin || linux

package releasecache

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
	"golang.org/x/sys/unix"
)

const (
	releasesDirectory = "releases"
	stagingPrefix     = ".staging-"
)

type Entry struct {
	Path           string
	ReleaseID      string
	IndexSHA256    string
	AlreadyPresent bool
}

type Store struct {
	root     string
	copyTree func(string, string) error
}

func New(root string) (Store, error) {
	if root == "" || strings.ContainsRune(root, '\x00') ||
		!filepath.IsAbs(root) || filepath.Clean(root) != root ||
		filepath.Base(root) != "mainframe" {
		return Store{}, fmt.Errorf(
			"release store root must be an absolute, clean, NUL-free mainframe directory",
		)
	}
	canonical, err := canonicalCreationPath(root)
	if err != nil {
		return Store{}, err
	}
	return Store{root: canonical, copyTree: copyTree}, nil
}

func (store Store) Import(source string) (Entry, error) {
	if store.root == "" || store.copyTree == nil {
		return Entry{}, fmt.Errorf("release store is not initialized")
	}
	accepted, err := releasecontract.Load(source)
	if err != nil {
		return Entry{}, fmt.Errorf("validate source release: %w", err)
	}
	versionParent, err := store.prepare(accepted.ID)
	if err != nil {
		return Entry{}, err
	}
	lock, err := acquireLock(filepath.Join(store.root, releasesDirectory))
	if err != nil {
		return Entry{}, err
	}
	defer lock.release()

	entry := store.entry(accepted, versionParent)
	if exists, err := validateExisting(entry); exists || err != nil {
		entry.AlreadyPresent = exists && err == nil
		return entry, err
	}
	return store.importNew(source, accepted, versionParent, entry)
}

func (store Store) Open(releaseID, indexSHA256 string) (Entry, error) {
	if store.root == "" || store.copyTree == nil {
		return Entry{}, fmt.Errorf("release store is not initialized")
	}
	if !releasecontract.ValidReleaseIdentity(releaseID, indexSHA256) {
		return Entry{}, fmt.Errorf("release identity is invalid")
	}
	entry := Entry{
		Path: filepath.Join(
			store.root,
			releasesDirectory,
			releaseID,
			indexSHA256,
		),
		ReleaseID:      releaseID,
		IndexSHA256:    indexSHA256,
		AlreadyPresent: true,
	}
	exists, err := validateExisting(entry)
	if err != nil {
		return Entry{}, err
	}
	if !exists {
		return Entry{}, fmt.Errorf("release version was not found")
	}
	return entry, nil
}

func (store Store) importNew(
	source string,
	accepted releasecontract.Release,
	versionParent string,
	entry Entry,
) (Entry, error) {
	staging, err := os.MkdirTemp(versionParent, stagingPrefix)
	if err != nil {
		return Entry{}, fmt.Errorf("create release staging directory: %w", err)
	}
	if err := os.Chmod(staging, 0o700); err != nil {
		_ = os.RemoveAll(staging)
		return Entry{}, fmt.Errorf("secure release staging directory: %w", err)
	}
	publishedPath := false
	defer func() {
		if !publishedPath {
			_ = os.RemoveAll(staging)
		}
	}()
	if err := store.copyTree(source, staging); err != nil {
		return Entry{}, fmt.Errorf("copy source release: %w", err)
	}
	copied, err := releasecontract.Load(staging)
	if err != nil {
		return Entry{}, fmt.Errorf("validate copied release: %w", err)
	}
	if copied.ID != accepted.ID || copied.IndexSHA256 != accepted.IndexSHA256 {
		return Entry{}, fmt.Errorf("source changed while importing release")
	}
	published, err := publishNoReplace(versionParent, filepath.Base(staging), copied.IndexSHA256)
	if err != nil {
		return Entry{}, err
	}
	if published {
		publishedPath = true
		return entry, nil
	}
	entry.AlreadyPresent = true
	_, err = validateExisting(entry)
	return entry, err
}

func (store Store) prepare(releaseID string) (string, error) {
	releases := filepath.Join(store.root, releasesDirectory)
	for _, directory := range []string{store.root, releases, filepath.Join(releases, releaseID)} {
		if err := ensurePrivateDirectory(directory); err != nil {
			return "", err
		}
	}
	return filepath.Join(releases, releaseID), nil
}

func (store Store) entry(release releasecontract.Release, parent string) Entry {
	return Entry{
		Path:        filepath.Join(parent, release.IndexSHA256),
		ReleaseID:   release.ID,
		IndexSHA256: release.IndexSHA256,
	}
}

func validateExisting(entry Entry) (bool, error) {
	info, err := os.Lstat(entry.Path)
	if errors.Is(err, fs.ErrNotExist) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("inspect existing release: %w", err)
	}
	if info.Mode()&fs.ModeSymlink != 0 || !info.IsDir() {
		return true, fmt.Errorf("existing release path is not a real directory")
	}
	resolved, err := filepath.EvalSymlinks(entry.Path)
	if err != nil {
		return true, fmt.Errorf("resolve existing release path: %w", err)
	}
	if resolved != entry.Path {
		return true, fmt.Errorf("existing release path escapes the canonical store")
	}
	release, err := releasecontract.Load(entry.Path)
	if err != nil {
		return true, fmt.Errorf("validate existing release: %w", err)
	}
	if release.ID != entry.ReleaseID || release.IndexSHA256 != entry.IndexSHA256 {
		return true, fmt.Errorf("existing release identity mismatch")
	}
	return true, nil
}

func ensurePrivateDirectory(path string) error {
	descriptor, err := openOrCreateDirectoryPath(path)
	if err != nil {
		return err
	}
	defer unix.Close(descriptor)
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return fmt.Errorf("inspect release store directory %q: %w", path, err)
	}
	if int(metadata.Uid) != os.Geteuid() {
		return fmt.Errorf("release store directory %q is not owned by the current user", path)
	}
	if err := unix.Fchmod(descriptor, 0o700); err != nil {
		return fmt.Errorf("secure release store directory %q: %w", path, err)
	}
	if err := unix.Fsync(descriptor); err != nil {
		return fmt.Errorf("sync release store directory %q: %w", path, err)
	}
	return nil
}
