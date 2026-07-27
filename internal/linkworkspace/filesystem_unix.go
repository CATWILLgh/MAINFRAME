//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

const (
	directoryOpenFlags = unix.O_RDONLY | unix.O_DIRECTORY | unix.O_CLOEXEC | unix.O_NOFOLLOW
	maxLinkTargetBytes = 64 * 1024
)

type pinnedRoot struct {
	path     string
	identity executor.FileIdentity
}

type managedRoot struct {
	anchor   pinnedRoot
	rootPath string
}

func pinRoot(path string) (pinnedRoot, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return pinnedRoot{}, fmt.Errorf("make root absolute: %w", err)
	}
	canonical, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return pinnedRoot{}, fmt.Errorf("resolve root: %w", err)
	}
	fd, err := openAbsoluteDirectory(canonical)
	if err != nil {
		return pinnedRoot{}, fmt.Errorf("open root: %w", err)
	}
	defer unix.Close(fd)
	identity, err := identityOfFD(fd)
	if err != nil {
		return pinnedRoot{}, fmt.Errorf("identify root: %w", err)
	}
	return pinnedRoot{path: canonical, identity: identity}, nil
}

func (root pinnedRoot) open() (int, error) {
	fd, err := openAbsoluteDirectory(root.path)
	if err != nil {
		return -1, err
	}
	actual, err := identityOfFD(fd)
	if err != nil {
		unix.Close(fd)
		return -1, err
	}
	if actual != root.identity {
		unix.Close(fd)
		return -1, errors.New("pinned root identity changed")
	}
	return fd, nil
}

func pinManagedRoot(target string) (managedRoot, error) {
	absolute, err := filepath.Abs(target)
	if err != nil {
		return managedRoot{}, fmt.Errorf("make managed root absolute: %w", err)
	}
	absolute = filepath.Clean(absolute)
	existing := absolute
	for {
		_, err = os.Lstat(existing)
		if err == nil {
			break
		}
		if !errors.Is(err, os.ErrNotExist) {
			return managedRoot{}, fmt.Errorf("inspect managed root ancestor: %w", err)
		}
		parent := filepath.Dir(existing)
		if parent == existing {
			return managedRoot{}, errors.New("managed root has no existing ancestor")
		}
		existing = parent
	}
	anchor, err := pinRoot(existing)
	if err != nil {
		return managedRoot{}, err
	}
	remainder, err := filepath.Rel(existing, absolute)
	if err != nil {
		return managedRoot{}, fmt.Errorf("derive managed root path: %w", err)
	}
	if remainder == "." {
		remainder = ""
	}
	return managedRoot{
		anchor:   anchor,
		rootPath: filepath.ToSlash(remainder),
	}, nil
}

func (root managedRoot) open() (int, error) {
	fd, err := root.anchor.open()
	if err != nil {
		return -1, err
	}
	if root.rootPath == "" {
		return fd, nil
	}
	opened, err := openRelativeDirectory(fd, strings.Split(root.rootPath, "/"))
	unix.Close(fd)
	return opened, err
}

func (root managedRoot) snapshot(id domain.RootID) executor.RootSnapshot {
	return executor.RootSnapshot{
		Root:           id,
		AnchorPath:     root.anchor.path,
		AnchorIdentity: root.anchor.identity,
		RootPath:       root.rootPath,
	}
}

func (root managedRoot) absolute() string {
	if root.rootPath == "" {
		return root.anchor.path
	}
	return filepath.Join(root.anchor.path, filepath.FromSlash(root.rootPath))
}

func openAbsoluteDirectory(path string) (int, error) {
	if !filepath.IsAbs(path) {
		return -1, errors.New("directory path is not absolute")
	}
	fd, err := unix.Open(string(filepath.Separator), directoryOpenFlags, 0)
	if err != nil {
		return -1, err
	}
	for _, segment := range splitAbsolutePath(path) {
		next, openErr := unix.Openat(fd, segment, directoryOpenFlags, 0)
		unix.Close(fd)
		if openErr != nil {
			return -1, openErr
		}
		fd = next
	}
	return fd, nil
}

func splitAbsolutePath(path string) []string {
	cleaned := filepath.Clean(path)
	trimmed := strings.TrimPrefix(cleaned, string(filepath.Separator))
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, string(filepath.Separator))
}

func openRelativeDirectory(rootFD int, segments []string) (int, error) {
	fd, err := unix.Dup(rootFD)
	if err != nil {
		return -1, err
	}
	unix.CloseOnExec(fd)
	for _, segment := range segments {
		next, openErr := unix.Openat(fd, segment, directoryOpenFlags, 0)
		unix.Close(fd)
		if openErr != nil {
			return -1, openErr
		}
		fd = next
	}
	return fd, nil
}

func identityOfFD(fd int) (executor.FileIdentity, error) {
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		return executor.FileIdentity{}, err
	}
	return identityFromFD(fd, stat)
}

func identityAt(parentFD int, name string) (executor.FileIdentity, uint32, error) {
	var stat unix.Stat_t
	if err := unix.Fstatat(parentFD, name, &stat, unix.AT_SYMLINK_NOFOLLOW); err != nil {
		return executor.FileIdentity{}, 0, err
	}
	identity, err := identityFromName(parentFD, name, stat)
	return identity, uint32(stat.Mode), err
}

func readLinkAt(parentFD int, name string) (string, error) {
	size := 256
	for size <= maxLinkTargetBytes {
		buffer := make([]byte, size)
		count, err := unix.Readlinkat(parentFD, name, buffer)
		if err != nil {
			return "", err
		}
		if count < len(buffer) {
			return string(buffer[:count]), nil
		}
		size *= 2
	}
	return "", errors.New("symbolic-link target is too long")
}

func directoryEmpty(fd int) (bool, error) {
	duplicate, err := unix.Dup(fd)
	if err != nil {
		return false, err
	}
	file := os.NewFile(uintptr(duplicate), "private-directory")
	if file == nil {
		unix.Close(duplicate)
		return false, errors.New("wrap directory descriptor")
	}
	defer file.Close()
	_, err = file.Readdirnames(1)
	if errors.Is(err, io.EOF) {
		return true, nil
	}
	return false, err
}

func syncDirectory(fd int) error {
	if err := unix.Fsync(fd); err != nil {
		return fmt.Errorf("sync directory: %w", err)
	}
	return nil
}

func isMissing(err error) bool {
	return errors.Is(err, unix.ENOENT)
}

func fileType(mode uint32) uint32 {
	return mode & unix.S_IFMT
}
