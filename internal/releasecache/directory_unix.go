//go:build darwin || linux

package releasecache

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/sys/unix"
)

func canonicalCreationPath(path string) (string, error) {
	current := path
	missing := make([]string, 0)
	for {
		info, err := os.Lstat(current)
		if err == nil {
			if current == path && info.Mode()&fs.ModeSymlink != 0 {
				return "", fmt.Errorf("release store root must not be a symbolic link")
			}
			resolved, err := filepath.EvalSymlinks(current)
			if err != nil {
				return "", fmt.Errorf("resolve release store ancestor %q: %w", current, err)
			}
			for index := len(missing) - 1; index >= 0; index-- {
				resolved = filepath.Join(resolved, missing[index])
			}
			return resolved, nil
		}
		if !errors.Is(err, fs.ErrNotExist) {
			return "", fmt.Errorf("inspect release store ancestor %q: %w", current, err)
		}
		parent := filepath.Dir(current)
		if parent == current {
			return "", fmt.Errorf("release store has no existing filesystem ancestor")
		}
		missing = append(missing, filepath.Base(current))
		current = parent
	}
}

func openOrCreateDirectoryPath(path string) (int, error) {
	current, err := unix.Open(
		string(filepath.Separator),
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, fmt.Errorf("open filesystem root: %w", err)
	}
	for _, segment := range strings.Split(strings.TrimPrefix(path, string(filepath.Separator)), string(filepath.Separator)) {
		next, err := openOrCreateChildDirectory(current, segment)
		_ = unix.Close(current)
		if err != nil {
			return -1, err
		}
		current = next
	}
	return current, nil
}

func openOrCreateChildDirectory(parent int, name string) (int, error) {
	next, err := unix.Openat(
		parent, name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err == nil {
		return syncedChild(parent, next, name)
	}
	if !errors.Is(err, unix.ENOENT) {
		return -1, fmt.Errorf("open release store directory %q: %w", name, err)
	}
	if err := unix.Mkdirat(parent, name, 0o700); err != nil && !errors.Is(err, unix.EEXIST) {
		return -1, fmt.Errorf("create release store directory %q: %w", name, err)
	}
	next, err = unix.Openat(
		parent, name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, fmt.Errorf("open created release store directory %q: %w", name, err)
	}
	return syncedChild(parent, next, name)
}

func syncedChild(parent, child int, name string) (int, error) {
	if err := unix.Fsync(parent); err != nil {
		_ = unix.Close(child)
		return -1, fmt.Errorf("sync parent of release store directory %q: %w", name, err)
	}
	return child, nil
}
