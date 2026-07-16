package releasecontract

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func canonicalRoot(root string) (string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", fmt.Errorf("resolve release root: %w", err)
	}
	if filepath.Clean(root) != root && filepath.Clean(absolute) != root {
		return "", fmt.Errorf("release root must be a clean path")
	}
	info, err := os.Lstat(absolute)
	if err != nil {
		return "", fmt.Errorf("inspect release root: %w", err)
	}
	if info.Mode()&fs.ModeSymlink != 0 || !info.IsDir() {
		return "", fmt.Errorf("release root must be a real directory")
	}
	resolved, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return "", fmt.Errorf("resolve release root links: %w", err)
	}
	return resolved, nil
}

func readRegular(root, relative string) ([]byte, error) {
	path, err := safePath(root, relative)
	if err != nil {
		return nil, err
	}
	info, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if info.Mode()&fs.ModeSymlink != 0 || !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%s must be a regular file", relative)
	}
	return os.ReadFile(path)
}

func safePath(root, relative string) (string, error) {
	if !domain.ArtifactPath(relative).Portable() {
		return "", fmt.Errorf("invalid release path %q", relative)
	}
	current := root
	for _, segment := range strings.Split(relative, "/") {
		current = filepath.Join(current, segment)
		info, err := os.Lstat(current)
		if err != nil {
			return "", err
		}
		if info.Mode()&fs.ModeSymlink != 0 {
			return "", fmt.Errorf("release path %q contains a symbolic link", relative)
		}
	}
	return current, nil
}

func payloadInventory(bundleRoot string) ([]payloadFile, error) {
	rows := make([]payloadFile, 0)
	err := filepath.WalkDir(bundleRoot, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path == bundleRoot {
			return nil
		}
		relative, err := filepath.Rel(bundleRoot, path)
		if err != nil {
			return err
		}
		relative = filepath.ToSlash(relative)
		if entry.Type()&fs.ModeSymlink != 0 {
			return fmt.Errorf("bundle payload contains symbolic link %q", relative)
		}
		if entry.IsDir() || relative == "bundle.json" {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("bundle payload contains non-regular file %q", relative)
		}
		digest, err := digestPath(path)
		if err != nil {
			return err
		}
		rows = append(rows, payloadFile{
			Path: relative, Mode: fmt.Sprintf("%04o", info.Mode().Perm()),
			Size: info.Size(), SHA256: digest,
		})
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Path < rows[j].Path })
	return rows, nil
}

func validateClosedReleaseTree(
	root string,
	index releaseIndex,
	manifests []bundleManifest,
) error {
	expected := expectedReleaseTree(index, manifests)
	seen := make(map[string]bool, len(expected))
	err := filepath.WalkDir(root, func(current string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if current == root {
			return nil
		}
		relative, err := filepath.Rel(root, current)
		if err != nil {
			return err
		}
		relative = filepath.ToSlash(relative)
		wantDirectory, exists := expected[relative]
		if !exists {
			return fmt.Errorf("release tree contains unindexed entry %q", relative)
		}
		if entry.IsDir() != wantDirectory {
			return fmt.Errorf("release tree entry %q has unexpected kind", relative)
		}
		seen[relative] = true
		return nil
	})
	if err != nil {
		return err
	}
	for relative := range expected {
		if !seen[relative] {
			return fmt.Errorf("release tree is missing indexed entry %q", relative)
		}
	}
	return nil
}

func expectedReleaseTree(
	index releaseIndex,
	manifests []bundleManifest,
) map[string]bool {
	expected := map[string]bool{"release.json": false}
	for position, entry := range index.Manifests {
		addExpectedFile(expected, entry.Path)
		base := path.Dir(entry.Path)
		for _, payload := range manifests[position].PayloadFiles {
			addExpectedFile(expected, path.Join(base, payload.Path))
		}
	}
	return expected
}

func addExpectedFile(expected map[string]bool, relative string) {
	expected[relative] = false
	for parent := path.Dir(relative); parent != "."; parent = path.Dir(parent) {
		expected[parent] = true
	}
}

func digestPath(path string) (string, error) {
	payload, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return digestBytes(payload), nil
}

func digestBytes(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}
