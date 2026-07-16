//go:build darwin || linux

package releasecache

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"sort"

	"golang.org/x/sys/unix"
)

func copyTree(source, destination string) error {
	sourceFD, err := unix.Open(
		source,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return fmt.Errorf("open source root: %w", err)
	}
	destinationFD, err := openEmptyDestination(destination)
	if err != nil {
		_ = unix.Close(sourceFD)
		return err
	}
	return copyDirectory(sourceFD, destinationFD)
}

func openEmptyDestination(path string) (int, error) {
	if err := os.Mkdir(path, 0o700); err != nil && !os.IsExist(err) {
		return -1, fmt.Errorf("create destination root: %w", err)
	}
	descriptor, err := unix.Open(
		path,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, fmt.Errorf("open destination root: %w", err)
	}
	entries, err := os.ReadDir(path)
	if err != nil || len(entries) != 0 {
		_ = unix.Close(descriptor)
		if err != nil {
			return -1, fmt.Errorf("inspect destination root: %w", err)
		}
		return -1, fmt.Errorf("destination root must be empty")
	}
	return descriptor, nil
}

func copyDirectory(sourceFD, destinationFD int) error {
	defer unix.Close(sourceFD)
	defer unix.Close(destinationFD)
	entries, err := readDirectory(sourceFD)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if err := copyEntry(sourceFD, destinationFD, entry.Name()); err != nil {
			return err
		}
	}
	var sourceMetadata unix.Stat_t
	if err := unix.Fstat(sourceFD, &sourceMetadata); err != nil {
		return fmt.Errorf("inspect source directory: %w", err)
	}
	if err := unix.Fchmod(destinationFD, uint32(sourceMetadata.Mode&0o777)); err != nil {
		return fmt.Errorf("preserve destination directory mode: %w", err)
	}
	if err := unix.Fsync(destinationFD); err != nil {
		return fmt.Errorf("sync destination directory: %w", err)
	}
	return nil
}

func readDirectory(descriptor int) ([]fs.DirEntry, error) {
	duplicate, err := unix.Dup(descriptor)
	if err != nil {
		return nil, fmt.Errorf("duplicate source directory descriptor: %w", err)
	}
	file := os.NewFile(uintptr(duplicate), "source-directory")
	if file == nil {
		_ = unix.Close(duplicate)
		return nil, fmt.Errorf("open source directory descriptor")
	}
	defer file.Close()
	entries, err := file.ReadDir(-1)
	if err != nil {
		return nil, fmt.Errorf("read source directory: %w", err)
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
	return entries, nil
}

func copyEntry(sourceFD, destinationFD int, name string) error {
	var metadata unix.Stat_t
	if err := unix.Fstatat(sourceFD, name, &metadata, unix.AT_SYMLINK_NOFOLLOW); err != nil {
		return fmt.Errorf("inspect source entry %q: %w", name, err)
	}
	switch metadata.Mode & unix.S_IFMT {
	case unix.S_IFDIR:
		return copyChildDirectory(sourceFD, destinationFD, name)
	case unix.S_IFREG:
		return copyRegularFile(sourceFD, destinationFD, name)
	default:
		return fmt.Errorf("source entry %q is not a regular file or directory", name)
	}
}

func copyChildDirectory(sourceFD, destinationFD int, name string) error {
	if err := unix.Mkdirat(destinationFD, name, 0o700); err != nil {
		return fmt.Errorf("create destination directory %q: %w", name, err)
	}
	sourceChild, err := unix.Openat(
		sourceFD, name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return fmt.Errorf("open source directory %q: %w", name, err)
	}
	destinationChild, err := unix.Openat(
		destinationFD, name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		_ = unix.Close(sourceChild)
		return fmt.Errorf("open destination directory %q: %w", name, err)
	}
	return copyDirectory(sourceChild, destinationChild)
}

func copyRegularFile(sourceFD, destinationFD int, name string) error {
	input, metadata, err := openSourceFile(sourceFD, name)
	if err != nil {
		return err
	}
	defer input.Close()
	outputFD, err := unix.Openat(
		destinationFD, name,
		unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0o600,
	)
	if err != nil {
		return fmt.Errorf("create destination file %q: %w", name, err)
	}
	output := os.NewFile(uintptr(outputFD), name)
	if output == nil {
		_ = unix.Close(outputFD)
		return fmt.Errorf("open destination file %q", name)
	}
	return writeCopiedFile(output, input, os.FileMode(metadata.Mode&0o777), name)
}

func openSourceFile(parent int, name string) (*os.File, unix.Stat_t, error) {
	descriptor, err := unix.Openat(
		parent, name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return nil, unix.Stat_t{}, fmt.Errorf("open source file %q: %w", name, err)
	}
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		_ = unix.Close(descriptor)
		return nil, unix.Stat_t{}, fmt.Errorf("inspect source file %q: %w", name, err)
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFREG {
		_ = unix.Close(descriptor)
		return nil, unix.Stat_t{}, fmt.Errorf("source file %q changed type", name)
	}
	file := os.NewFile(uintptr(descriptor), name)
	if file == nil {
		_ = unix.Close(descriptor)
		return nil, unix.Stat_t{}, fmt.Errorf("open source file descriptor %q", name)
	}
	return file, metadata, nil
}

func writeCopiedFile(output, input *os.File, mode os.FileMode, name string) (result error) {
	defer func() {
		if err := output.Close(); result == nil && err != nil {
			result = fmt.Errorf("close copied file %q: %w", name, err)
		}
	}()
	if _, err := io.Copy(output, input); err != nil {
		return fmt.Errorf("copy file %q: %w", name, err)
	}
	if err := output.Chmod(mode); err != nil {
		return fmt.Errorf("preserve file mode %q: %w", name, err)
	}
	if err := output.Sync(); err != nil {
		return fmt.Errorf("sync copied file %q: %w", name, err)
	}
	return nil
}
