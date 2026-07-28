//go:build darwin || linux

package releasecache

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"

	"golang.org/x/sys/unix"
)

func validateSealedFiles(root string) error {
	return filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		return rejectWritableEntry(path, entry)
	})
}

func sealStagedDirectories(root string) error {
	var directories []string
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() && path != root {
			directories = append(directories, path)
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("inspect staged release directories: %w", err)
	}
	for index := len(directories) - 1; index >= 0; index-- {
		if err := os.Chmod(directories[index], 0o555); err != nil {
			return fmt.Errorf("seal staged release directory: %w", err)
		}
	}
	return nil
}

func validateSealedTree(root string, allowWritableRoot bool) error {
	return filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if allowWritableRoot && path == root {
			return nil
		}
		return rejectWritableEntry(path, entry)
	})
}

func rejectWritableEntry(path string, entry fs.DirEntry) error {
	info, err := entry.Info()
	if err != nil {
		return err
	}
	if info.Mode().Perm()&0o222 != 0 {
		return fmt.Errorf("release is not sealed: %q is writable", path)
	}
	return nil
}

func sealReleaseRoot(path string) error {
	descriptor, err := unix.Open(
		path,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return err
	}
	defer unix.Close(descriptor)
	if err := unix.Fchmod(descriptor, 0o555); err != nil {
		return err
	}
	return unix.Fsync(descriptor)
}

func removeTree(root string) error {
	_ = filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			_ = os.Chmod(path, 0o700)
		}
		return nil
	})
	return os.RemoveAll(root)
}

func cleanupPublished(root string) error {
	if err := removeTree(root); err != nil {
		return fmt.Errorf("remove failed release publication: %w", err)
	}
	parent, err := unix.Open(
		filepath.Dir(root),
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return fmt.Errorf("open release publication parent after cleanup: %w", err)
	}
	defer unix.Close(parent)
	if err := unix.Fsync(parent); err != nil {
		return fmt.Errorf("sync release publication cleanup: %w", err)
	}
	return nil
}
