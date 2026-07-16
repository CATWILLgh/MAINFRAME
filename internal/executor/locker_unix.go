//go:build unix

package executor

import (
	"fmt"
	"os"
	"sync"

	"golang.org/x/sys/unix"
)

type unixLock struct {
	mutex sync.Mutex
	file  *os.File
}

func (state *UnixState) Lock() (Lock, error) {
	directory, err := state.directoryDescriptor()
	if err != nil {
		return nil, err
	}
	descriptor, err := unix.Openat(
		directory,
		lockFileName,
		unix.O_RDWR|unix.O_CREAT|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0o600,
	)
	if err != nil {
		return nil, fmt.Errorf("open transaction lock: %w", err)
	}
	file := os.NewFile(uintptr(descriptor), lockFileName)
	if file == nil {
		unix.Close(descriptor)
		return nil, fmt.Errorf("open transaction lock: invalid descriptor")
	}
	if err := secureOwnedFile(descriptor); err != nil {
		file.Close()
		return nil, fmt.Errorf("secure transaction lock: %w", err)
	}
	if err := unix.Flock(descriptor, unix.LOCK_EX|unix.LOCK_NB); err != nil {
		file.Close()
		return nil, fmt.Errorf("acquire transaction lock: %w", err)
	}
	return &unixLock{file: file}, nil
}

func (lock *unixLock) Unlock() error {
	lock.mutex.Lock()
	defer lock.mutex.Unlock()
	if lock.file == nil {
		return fmt.Errorf("transaction lock is already released")
	}
	descriptor := int(lock.file.Fd())
	unlockErr := unix.Flock(descriptor, unix.LOCK_UN)
	closeErr := lock.file.Close()
	lock.file = nil
	if unlockErr != nil {
		return fmt.Errorf("release transaction lock: %w", unlockErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close transaction lock: %w", closeErr)
	}
	return nil
}

func secureOwnedFile(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return err
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFREG {
		return fmt.Errorf("state file is not regular")
	}
	if int(metadata.Uid) != os.Geteuid() {
		return fmt.Errorf("state file is not owned by the current user")
	}
	return unix.Fchmod(descriptor, 0o600)
}
