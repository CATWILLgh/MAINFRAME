//go:build unix

package executor

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"golang.org/x/sys/unix"
)

const (
	ownershipFileName   = "link-ownership.json"
	ownershipTempPrefix = ".link-ownership-"
)

func (state *UnixState) LoadOwnership() (linkownership.Registry, error) {
	directory, err := state.directoryDescriptor()
	if err != nil {
		return linkownership.Registry{}, err
	}
	return loadOwnershipFromDirectory(directory)
}

func ReadUnixOwnership(root string) (linkownership.Registry, error) {
	if err := validateStateRoot(root); err != nil {
		return linkownership.Registry{}, err
	}
	if _, err := os.Lstat(root); errors.Is(err, os.ErrNotExist) {
		return linkownership.New(nil)
	} else if err != nil {
		return linkownership.Registry{}, fmt.Errorf("inspect state root: %w", err)
	}
	directory, err := openExistingStateDirectory(root)
	if errors.Is(err, unix.ENOENT) {
		return linkownership.New(nil)
	}
	if err != nil {
		return linkownership.Registry{}, err
	}
	defer unix.Close(directory)
	if err := validateStateDirectory(directory); err != nil {
		return linkownership.Registry{}, err
	}
	return loadOwnershipFromDirectory(directory)
}

func loadOwnershipFromDirectory(directory int) (linkownership.Registry, error) {
	descriptor, err := unix.Openat(
		directory, ownershipFileName,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0,
	)
	if errors.Is(err, unix.ENOENT) {
		return linkownership.New(nil)
	}
	if err != nil {
		return linkownership.Registry{}, fmt.Errorf("open ownership registry: %w", err)
	}
	file := os.NewFile(uintptr(descriptor), ownershipFileName)
	if file == nil {
		unix.Close(descriptor)
		return linkownership.Registry{}, errors.New("open ownership registry descriptor")
	}
	defer file.Close()
	if err := validateOwnershipFile(descriptor); err != nil {
		return linkownership.Registry{}, err
	}
	payload, err := io.ReadAll(io.LimitReader(file, linkownership.MaxRegistryBytes+1))
	if err != nil {
		return linkownership.Registry{}, fmt.Errorf("read ownership registry: %w", err)
	}
	return linkownership.Decode(payload)
}

func (state *UnixState) SaveOwnership(registry linkownership.Registry) error {
	payload, err := linkownership.Encode(registry)
	if err != nil {
		return err
	}
	directory, err := state.directoryDescriptor()
	if err != nil {
		return err
	}
	name, file, err := createOwnershipTemp(directory)
	if err != nil {
		return err
	}
	renamed := false
	defer func() {
		file.Close()
		if !renamed {
			unix.Unlinkat(directory, name, 0)
		}
	}()
	if err := writeAndSync(file, payload); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close ownership registry: %w", err)
	}
	if err := unix.Renameat(directory, name, directory, ownershipFileName); err != nil {
		return fmt.Errorf("publish ownership registry: %w", err)
	}
	renamed = true
	return syncStateDirectory(directory)
}

func createOwnershipTemp(directory int) (string, *os.File, error) {
	for attempt := 0; attempt < 8; attempt++ {
		random := make([]byte, 8)
		if _, err := rand.Read(random); err != nil {
			return "", nil, err
		}
		name := ownershipTempPrefix + hex.EncodeToString(random)
		fd, err := unix.Openat(
			directory, name,
			unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
			0o600,
		)
		if errors.Is(err, unix.EEXIST) {
			continue
		}
		if err != nil {
			return "", nil, fmt.Errorf("create ownership registry: %w", err)
		}
		file := os.NewFile(uintptr(fd), name)
		if file == nil {
			unix.Close(fd)
			return "", nil, errors.New("create ownership registry descriptor")
		}
		if err := secureOwnedFile(fd); err != nil {
			file.Close()
			unix.Unlinkat(directory, name, 0)
			return "", nil, err
		}
		return name, file, nil
	}
	return "", nil, errors.New("ownership registry name collision limit reached")
}

func validateOwnershipFile(descriptor int) error {
	var metadata unix.Stat_t
	if err := unix.Fstat(descriptor, &metadata); err != nil {
		return err
	}
	if metadata.Mode&unix.S_IFMT != unix.S_IFREG ||
		int(metadata.Uid) != os.Geteuid() || metadata.Mode&0o777 != 0o600 {
		return errors.New("ownership registry metadata is unsafe")
	}
	if metadata.Size > linkownership.MaxRegistryBytes {
		return errors.New("ownership registry is too large")
	}
	return nil
}

func syncStateDirectory(directory int) error {
	if err := unix.Fsync(directory); err != nil {
		return fmt.Errorf("sync state directory: %w", err)
	}
	return nil
}
