//go:build darwin || linux

package hostfs

import (
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/sys/unix"
)

const maxInspectedFileSize = 1 << 20

func inspectNoFollow(root, relative string, includeContent bool) (Entry, error) {
	segments := append(strings.Split(root, "/"), strings.Split(relative, "/")...)
	parent, err := unix.Open("/", unix.O_RDONLY|unix.O_DIRECTORY|unix.O_CLOEXEC, 0)
	if err != nil {
		return Entry{}, err
	}
	defer func() { _ = unix.Close(parent) }()
	for _, segment := range segments[:len(segments)-1] {
		if segment == "" {
			continue
		}
		next, err := openDirectoryNoFollow(parent, segment)
		if err != nil {
			return Entry{}, err
		}
		unix.Close(parent)
		parent = next
	}
	name := segments[len(segments)-1]
	var metadata unix.Stat_t
	if err := unix.Fstatat(parent, name, &metadata, unix.AT_SYMLINK_NOFOLLOW); err != nil {
		return Entry{}, err
	}
	kind := entryKind(uint32(metadata.Mode))
	entry := Entry{Kind: kind}
	if kind == EntryDirectory {
		if err := verifyDirectoryNoFollow(parent, name, metadata); err != nil {
			return Entry{}, err
		}
		return entry, nil
	}
	if kind == EntryRegular {
		content, err := inspectRegularNoFollow(parent, name, includeContent, metadata)
		if err != nil {
			return Entry{}, err
		}
		entry.Content = content
	}
	return entry, nil
}

func openDirectoryNoFollow(parent int, name string) (int, error) {
	var metadata unix.Stat_t
	if err := unix.Fstatat(parent, name, &metadata, unix.AT_SYMLINK_NOFOLLOW); err != nil {
		return -1, err
	}
	if entryKind(uint32(metadata.Mode)) == EntrySymlink {
		return -1, fmt.Errorf("path ancestor %q is a symbolic link", name)
	}
	if entryKind(uint32(metadata.Mode)) != EntryDirectory {
		return -1, fmt.Errorf("path ancestor %q is not a directory", name)
	}
	file, err := unix.Openat(
		parent,
		name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, err
	}
	var opened unix.Stat_t
	if err := unix.Fstat(file, &opened); err != nil {
		unix.Close(file)
		return -1, err
	}
	if !sameEntry(metadata, opened) {
		unix.Close(file)
		return -1, fmt.Errorf("path ancestor %q changed while being inspected", name)
	}
	return file, nil
}

func verifyDirectoryNoFollow(parent int, name string, expected unix.Stat_t) error {
	descriptor, err := unix.Openat(
		parent,
		name,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return err
	}
	defer unix.Close(descriptor)
	var opened unix.Stat_t
	if err := unix.Fstat(descriptor, &opened); err != nil {
		return err
	}
	if !sameEntry(expected, opened) {
		return fmt.Errorf("%q changed while being inspected", name)
	}
	return nil
}

func inspectRegularNoFollow(
	parent int,
	name string,
	includeContent bool,
	expected unix.Stat_t,
) ([]byte, error) {
	descriptor, err := unix.Openat(
		parent,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(descriptor), name)
	if file == nil {
		unix.Close(descriptor)
		return nil, fmt.Errorf("open %q", name)
	}
	defer file.Close()
	var opened unix.Stat_t
	if err := unix.Fstat(descriptor, &opened); err != nil {
		return nil, err
	}
	if !sameEntry(expected, opened) || entryKind(uint32(opened.Mode)) != EntryRegular {
		return nil, fmt.Errorf("%q changed while being inspected", name)
	}
	if !includeContent {
		return nil, nil
	}
	content, err := io.ReadAll(io.LimitReader(file, maxInspectedFileSize+1))
	if err != nil {
		return nil, err
	}
	if len(content) > maxInspectedFileSize {
		return nil, fmt.Errorf("%q exceeds the inspection size limit", name)
	}
	return content, nil
}

func sameEntry(expected, opened unix.Stat_t) bool {
	return expected.Dev == opened.Dev && expected.Ino == opened.Ino
}

func entryKind(mode uint32) EntryKind {
	switch mode & unix.S_IFMT {
	case unix.S_IFREG:
		return EntryRegular
	case unix.S_IFDIR:
		return EntryDirectory
	case unix.S_IFLNK:
		return EntrySymlink
	default:
		return EntryOther
	}
}
