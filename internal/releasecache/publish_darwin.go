//go:build darwin

package releasecache

import (
	"errors"
	"fmt"

	"golang.org/x/sys/unix"
)

func publishNoReplace(parentPath, stagingName, destinationName string) (bool, error) {
	parent, err := unix.Open(
		parentPath,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return false, fmt.Errorf("open release publication directory: %w", err)
	}
	defer unix.Close(parent)
	err = unix.RenameatxNp(parent, stagingName, parent, destinationName, unix.RENAME_EXCL)
	if errors.Is(err, unix.EEXIST) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("publish release without replacement: %w", err)
	}
	if err := unix.Fsync(parent); err != nil {
		return true, fmt.Errorf("sync release publication directory: %w", err)
	}
	return true, nil
}
