package releaselayout

import (
	"fmt"
	"path/filepath"
)

type ExecutableFunc func() (string, error)
type EvalSymlinksFunc func(string) (string, error)

func Resolve(
	explicit string,
	hasExplicit bool,
	executable ExecutableFunc,
	evalSymlinks EvalSymlinksFunc,
) (string, error) {
	if hasExplicit {
		if explicit == "" {
			return "", fmt.Errorf("explicit release root must not be empty")
		}
		if !filepath.IsAbs(explicit) || filepath.Clean(explicit) != explicit {
			return "", fmt.Errorf("explicit release root must be an absolute clean path")
		}
		resolved, err := evalSymlinks(explicit)
		if err != nil {
			return "", fmt.Errorf("resolve explicit release root: %w", err)
		}
		return resolved, nil
	}
	if executable == nil || evalSymlinks == nil {
		return "", fmt.Errorf("release executable resolvers must not be nil")
	}
	binary, err := executable()
	if err != nil {
		return "", fmt.Errorf("resolve executable: %w", err)
	}
	resolved, err := evalSymlinks(binary)
	if err != nil {
		return "", fmt.Errorf("resolve executable links: %w", err)
	}
	if !filepath.IsAbs(resolved) || filepath.Base(filepath.Dir(resolved)) != "bin" {
		return "", fmt.Errorf("resolved executable is not inside a release bin directory")
	}
	return filepath.Dir(filepath.Dir(resolved)), nil
}
