//go:build darwin || linux

package releasecache

import (
	"errors"
	"fmt"
	"os"

	"golang.org/x/sys/unix"
)

const lockFileName = ".lock"

type storeLock struct {
	file *os.File
}

func acquireLock(directory string) (*storeLock, error) {
	parent, err := unix.Open(
		directory,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return nil, fmt.Errorf("open release store for locking: %w", err)
	}
	defer unix.Close(parent)
	descriptor, err := createOrOpenLock(parent)
	if err != nil {
		return nil, fmt.Errorf("open release store lock: %w", err)
	}
	file := os.NewFile(uintptr(descriptor), lockFileName)
	if file == nil {
		_ = unix.Close(descriptor)
		return nil, fmt.Errorf("open release store lock descriptor")
	}
	if err := secureLock(descriptor); err != nil {
		file.Close()
		return nil, err
	}
	if err := unix.Flock(descriptor, unix.LOCK_EX); err != nil {
		file.Close()
		return nil, fmt.Errorf("acquire release store lock: %w", err)
	}
	return &storeLock{file: file}, nil
}

func createOrOpenLock(parent int) (int, error) {
	descriptor, err := unix.Openat(
		parent, lockFileName,
		unix.O_RDWR|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0o600,
	)
	if err == nil {
		return descriptor, nil
	}
	if !errors.Is(err, unix.EEXIST) {
		return -1, err
	}
	return unix.Openat(
		parent, lockFileName,
		unix.O_RDWR|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
}

func secureLock(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return fmt.Errorf("inspect release store lock: %w", err)
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFREG ||
		int(metadata.Uid) != os.Geteuid() ||
		metadata.Nlink != 1 {
		return fmt.Errorf(
			"release store lock must be a singly linked regular file owned by the current user",
		)
	}
	if err := unix.Fchmod(descriptor, 0o600); err != nil {
		return fmt.Errorf("secure release store lock: %w", err)
	}
	return nil
}

func (lock *storeLock) release() {
	if lock == nil || lock.file == nil {
		return
	}
	_ = unix.Flock(int(lock.file.Fd()), unix.LOCK_UN)
	_ = lock.file.Close()
	lock.file = nil
}
