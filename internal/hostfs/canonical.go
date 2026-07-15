package hostfs

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func canonicalFSPath(name, absolute string) (domain.ArtifactPath, error) {
	canonical, err := canonicalAbsolutePath(absolute)
	if err != nil {
		return "", fmt.Errorf("canonicalize %s %q: %w", name, absolute, err)
	}
	relative := strings.TrimPrefix(filepath.ToSlash(canonical), "/")
	artifactPath := domain.ArtifactPath(relative)
	if !artifactPath.Valid() || !fs.ValidPath(relative) {
		return "", fmt.Errorf("canonicalize %s %q: path cannot be represented in io/fs", name, absolute)
	}
	return artifactPath, nil
}

func canonicalAbsolutePath(absolute string) (string, error) {
	if absolute == "" || strings.ContainsRune(absolute, '\x00') || !filepath.IsAbs(absolute) || filepath.Clean(absolute) != absolute {
		return "", fmt.Errorf("invalid absolute path")
	}
	ancestor, suffix, err := deepestExistingAncestor(absolute)
	if err != nil {
		return "", err
	}
	canonical, err := filepath.EvalSymlinks(ancestor)
	if err != nil {
		return "", fmt.Errorf("evaluate symlink ancestor %q: %w", ancestor, err)
	}
	info, err := os.Stat(canonical)
	if err != nil {
		return "", fmt.Errorf("inspect resolved ancestor %q: %w", canonical, err)
	}
	if !info.IsDir() {
		return "", fmt.Errorf("resolved ancestor %q is not a directory", canonical)
	}
	for index := len(suffix) - 1; index >= 0; index-- {
		canonical = filepath.Join(canonical, suffix[index])
	}
	return canonical, nil
}

func deepestExistingAncestor(absolute string) (string, []string, error) {
	candidate := absolute
	var suffix []string
	for {
		_, err := os.Lstat(candidate)
		if err == nil {
			return candidate, suffix, nil
		}
		if !errors.Is(err, fs.ErrNotExist) {
			return "", nil, fmt.Errorf("inspect ancestor %q: %w", candidate, err)
		}
		parent := filepath.Dir(candidate)
		if parent == candidate {
			return "", nil, fmt.Errorf("no existing ancestor for %q", absolute)
		}
		suffix = append(suffix, filepath.Base(candidate))
		candidate = parent
	}
}
