package installsource

import (
	"fmt"
	"io/fs"
	"path/filepath"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

type StatFunc func(string) (fs.FileInfo, error)

func Find(
	candidates []string,
	model installmodel.Model,
	stat StatFunc,
	lstat StatFunc,
) (string, error) {
	if stat == nil {
		return "", fmt.Errorf("source stat function must not be nil")
	}
	if lstat == nil {
		return "", fmt.Errorf("source lstat function must not be nil")
	}
	required := requiredSources(model)
	errorsByCandidate := make([]string, 0, len(candidates))
	seen := make(map[string]bool)
	for _, candidate := range candidates {
		if seen[candidate] {
			continue
		}
		seen[candidate] = true
		if err := validateRoot(candidate, required, stat, lstat); err != nil {
			errorsByCandidate = append(errorsByCandidate, err.Error())
			continue
		}
		return candidate, nil
	}
	if len(errorsByCandidate) == 0 {
		return "", fmt.Errorf("no MAINFRAME source root candidates")
	}
	return "", fmt.Errorf("no valid MAINFRAME source root: %s", strings.Join(errorsByCandidate, "; "))
}

func requiredSources(model installmodel.Model) []string {
	unique := make(map[string]bool)
	for _, artifact := range model.Artifacts() {
		if !artifact.LegacyOnly {
			unique[string(artifact.SourcePath)] = true
		}
	}
	sources := make([]string, 0, len(unique))
	for source := range unique {
		sources = append(sources, source)
	}
	sort.Strings(sources)
	return sources
}

func validateRoot(root string, required []string, stat StatFunc, lstat StatFunc) error {
	if !filepath.IsAbs(root) || filepath.Clean(root) != root || strings.ContainsRune(root, '\x00') {
		return fmt.Errorf("source root %q must be an absolute clean path", root)
	}
	info, err := lstat(root)
	if err != nil {
		return fmt.Errorf("inspect source root %q: %w", root, err)
	}
	if info.Mode()&fs.ModeSymlink != 0 {
		return fmt.Errorf("source root %q must not be a symbolic link", root)
	}
	if !info.IsDir() {
		return fmt.Errorf("source root %q must be a directory", root)
	}
	resolvedRoot, err := filepath.EvalSymlinks(root)
	if err != nil {
		return fmt.Errorf("resolve source root %q: %w", root, err)
	}
	if resolvedRoot != root {
		return fmt.Errorf("source root %q must not contain symbolic links", root)
	}
	for _, source := range required {
		path := filepath.Join(root, filepath.FromSlash(source))
		if _, err := stat(path); err != nil {
			return fmt.Errorf("source root %q is missing %s: %w", root, source, err)
		}
	}
	return nil
}
