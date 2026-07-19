//go:build unix

package executor

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/sys/unix"
)

const (
	lockFileName      = "transaction.lock"
	journalFileName   = "transaction.json"
	journalTempPrefix = ".transaction-"
	maxJournalBytes   = 1 << 20
)

type UnixState struct {
	directory *os.File
}

var _ Locker = (*UnixState)(nil)
var _ JournalStore = (*UnixState)(nil)

func OpenUnixState(root string) (*UnixState, error) {
	if err := validateStateRoot(root); err != nil {
		return nil, err
	}
	descriptor, err := openStateDirectory(root)
	if err != nil {
		return nil, err
	}
	directory := os.NewFile(uintptr(descriptor), root)
	if directory == nil {
		unix.Close(descriptor)
		return nil, fmt.Errorf("open state root: invalid descriptor")
	}
	if err := secureDirectory(descriptor); err != nil {
		directory.Close()
		return nil, fmt.Errorf("secure state root: %w", err)
	}
	return &UnixState{directory: directory}, nil
}

func openStateDirectory(root string) (int, error) {
	current, err := unix.Open(
		string(filepath.Separator),
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, fmt.Errorf("open filesystem root: %w", err)
	}
	components := strings.Split(strings.TrimPrefix(root, string(filepath.Separator)), string(filepath.Separator))
	for index, component := range components {
		next, created, err := openOrCreateDirectory(current, component)
		if err != nil {
			unix.Close(current)
			return -1, fmt.Errorf("open state root component %q: %w", component, err)
		}
		if created {
			if err := unix.Fsync(current); err != nil {
				unix.Close(next)
				unix.Close(current)
				return -1, fmt.Errorf("sync parent of state root component %q: %w", component, err)
			}
		}
		unix.Close(current)
		current = next
		if index == len(components)-1 {
			return current, nil
		}
	}
	unix.Close(current)
	return -1, fmt.Errorf("state root has no path components")
}

func openExistingStateDirectory(root string) (int, error) {
	current, err := unix.Open(
		string(filepath.Separator),
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return -1, fmt.Errorf("open filesystem root: %w", err)
	}
	components := strings.Split(
		strings.TrimPrefix(root, string(filepath.Separator)),
		string(filepath.Separator),
	)
	for _, component := range components {
		next, openErr := unix.Openat(
			current,
			component,
			unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
			0,
		)
		unix.Close(current)
		if openErr != nil {
			return -1, fmt.Errorf("open state root component %q: %w", component, openErr)
		}
		current = next
	}
	return current, nil
}

func openOrCreateDirectory(parent int, name string) (int, bool, error) {
	flags := unix.O_RDONLY | unix.O_DIRECTORY | unix.O_NOFOLLOW | unix.O_CLOEXEC
	descriptor, err := unix.Openat(parent, name, flags, 0)
	if err == nil {
		return descriptor, false, nil
	}
	if !errors.Is(err, unix.ENOENT) {
		return -1, false, err
	}
	created := true
	if err := unix.Mkdirat(parent, name, 0o700); err != nil {
		if !errors.Is(err, unix.EEXIST) {
			return -1, false, err
		}
		created = false
	}
	descriptor, err = unix.Openat(parent, name, flags, 0)
	if err != nil {
		return -1, false, err
	}
	return descriptor, created, nil
}

func (state *UnixState) Close() error {
	if state == nil || state.directory == nil {
		return nil
	}
	err := state.directory.Close()
	state.directory = nil
	return err
}

func validateStateRoot(root string) error {
	if root == "" || !filepath.IsAbs(root) || filepath.Clean(root) != root ||
		root == string(filepath.Separator) || strings.ContainsRune(root, 0) {
		return fmt.Errorf("unsafe state root %q", root)
	}
	return nil
}

func secureDirectory(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return err
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFDIR {
		return fmt.Errorf("state root is not a directory")
	}
	if int(metadata.Uid) != os.Geteuid() {
		return fmt.Errorf("state root is not owned by the current user")
	}
	if err := unix.Fchmod(descriptor, 0o700); err != nil {
		return err
	}
	return unix.Fsync(descriptor)
}

func validateStateDirectory(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return err
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFDIR ||
		int(metadata.Uid) != os.Geteuid() || metadata.Mode&0o777 != 0o700 {
		return errors.New("state root metadata is unsafe")
	}
	return nil
}

func (state *UnixState) directoryDescriptor() (int, error) {
	if state == nil || state.directory == nil {
		return -1, fmt.Errorf("state is closed")
	}
	return int(state.directory.Fd()), nil
}
