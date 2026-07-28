//go:build unix

package executor

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"

	"golang.org/x/sys/unix"
)

func (state *UnixState) Load() (*Journal, error) {
	directory, err := state.directoryDescriptor()
	if err != nil {
		return nil, err
	}
	return loadJournalFromDirectory(directory)
}

func ReadUnixJournal(root string) (*Journal, error) {
	if err := validateStateRoot(root); err != nil {
		return nil, err
	}
	if _, err := os.Lstat(root); errors.Is(err, os.ErrNotExist) {
		return nil, nil
	} else if err != nil {
		return nil, fmt.Errorf("inspect state root: %w", err)
	}
	directory, err := openExistingStateDirectory(root)
	if errors.Is(err, unix.ENOENT) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	defer unix.Close(directory)
	if err := validateStateDirectory(directory); err != nil {
		return nil, err
	}
	return loadJournalFromDirectory(directory)
}

func loadJournalFromDirectory(directory int) (*Journal, error) {
	descriptor, err := unix.Openat(
		directory,
		journalFileName,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if errors.Is(err, unix.ENOENT) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("open transaction journal: %w", err)
	}
	file := os.NewFile(uintptr(descriptor), journalFileName)
	if file == nil {
		unix.Close(descriptor)
		return nil, fmt.Errorf("open transaction journal: invalid descriptor")
	}
	defer file.Close()
	if err := validateJournalFile(descriptor); err != nil {
		return nil, err
	}
	payload, err := io.ReadAll(io.LimitReader(file, maxJournalBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read transaction journal: %w", err)
	}
	if len(payload) > maxJournalBytes {
		return nil, fmt.Errorf("transaction journal exceeds %d bytes", maxJournalBytes)
	}
	journal, err := decodeJournal(payload)
	if err != nil {
		return nil, fmt.Errorf("decode transaction journal: %w", err)
	}
	if err := validateJournal(journal); err != nil {
		return nil, fmt.Errorf("validate transaction journal: %w", err)
	}
	return &journal, nil
}

func (state *UnixState) Save(journal Journal) error {
	if err := validateJournal(journal); err != nil {
		return fmt.Errorf("validate transaction journal: %w", err)
	}
	payload, err := encodeJournal(journal)
	if err != nil {
		return fmt.Errorf("encode transaction journal: %w", err)
	}
	if len(payload) > maxJournalBytes {
		return fmt.Errorf("transaction journal exceeds %d bytes", maxJournalBytes)
	}
	directory, err := state.directoryDescriptor()
	if err != nil {
		return err
	}
	tempName, tempFile, err := createJournalTemp(directory)
	if err != nil {
		return err
	}
	renamed := false
	defer func() {
		if tempFile != nil {
			tempFile.Close()
		}
		if !renamed {
			unix.Unlinkat(directory, tempName, 0)
		}
	}()
	if err := writeAndSync(tempFile, payload); err != nil {
		return err
	}
	if err := tempFile.Close(); err != nil {
		return fmt.Errorf("close temporary journal: %w", err)
	}
	tempFile = nil
	if err := unix.Renameat(directory, tempName, directory, journalFileName); err != nil {
		return fmt.Errorf("publish transaction journal: %w", err)
	}
	renamed = true
	if err := unix.Fsync(directory); err != nil {
		return fmt.Errorf("sync state directory: %w", err)
	}
	return nil
}

func (state *UnixState) Cleanup() error {
	directory, err := state.directoryDescriptor()
	if err != nil {
		return err
	}
	err = unix.Unlinkat(directory, journalFileName, 0)
	if errors.Is(err, unix.ENOENT) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("remove transaction journal: %w", err)
	}
	if err := unix.Fsync(directory); err != nil {
		return fmt.Errorf("sync state directory: %w", err)
	}
	return nil
}

func createJournalTemp(directory int) (string, *os.File, error) {
	for attempt := 0; attempt < 8; attempt++ {
		suffix := make([]byte, 8)
		if _, err := rand.Read(suffix); err != nil {
			return "", nil, fmt.Errorf("generate journal temporary name: %w", err)
		}
		name := journalTempPrefix + hex.EncodeToString(suffix)
		descriptor, err := unix.Openat(
			directory,
			name,
			unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
			0o600,
		)
		if errors.Is(err, unix.EEXIST) {
			continue
		}
		if err != nil {
			return "", nil, fmt.Errorf("create temporary journal: %w", err)
		}
		file := os.NewFile(uintptr(descriptor), name)
		if file == nil {
			unix.Close(descriptor)
			return "", nil, fmt.Errorf("create temporary journal: invalid descriptor")
		}
		if err := secureOwnedFile(descriptor); err != nil {
			file.Close()
			unix.Unlinkat(directory, name, 0)
			return "", nil, fmt.Errorf("secure temporary journal: %w", err)
		}
		return name, file, nil
	}
	return "", nil, fmt.Errorf("create temporary journal: name collision limit reached")
}

func writeAndSync(file *os.File, payload []byte) error {
	written, err := file.Write(payload)
	if err != nil {
		return fmt.Errorf("write temporary journal: %w", err)
	}
	if written != len(payload) {
		return fmt.Errorf("write temporary journal: wrote %d of %d bytes", written, len(payload))
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync temporary journal: %w", err)
	}
	return nil
}

func validateJournalFile(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return fmt.Errorf("inspect transaction journal: %w", err)
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFREG {
		return fmt.Errorf("transaction journal is not regular")
	}
	if int(metadata.Uid) != os.Geteuid() {
		return fmt.Errorf("transaction journal is not owned by the current user")
	}
	if metadata.Mode&0o777 != 0o600 {
		return fmt.Errorf("transaction journal mode is %#o, want 0600", metadata.Mode&0o777)
	}
	if metadata.Size > maxJournalBytes {
		return fmt.Errorf("transaction journal exceeds %d bytes", maxJournalBytes)
	}
	return nil
}
