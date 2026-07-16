//go:build linux

package linkworkspace

import (
	"fmt"

	"golang.org/x/sys/unix"
)

const (
	linuxExtFamily = 0xef53
	linuxXFS       = 0x58465342
	linuxBtrfs     = 0x9123683e
	linuxTmpfs     = 0x01021994
	linuxOverlay   = 0x794c7630
	linuxZFS       = 0x2fc12fc1
	linuxRamfs     = 0x858458f6
)

func checkConfigurationFilesystem(fd int) error {
	var stat unix.Statfs_t
	if err := unix.Fstatfs(fd, &stat); err != nil {
		return fmt.Errorf("inspect configuration filesystem: %w", err)
	}
	switch uint64(stat.Type) {
	case linuxExtFamily, linuxXFS, linuxBtrfs, linuxTmpfs,
		linuxOverlay, linuxZFS, linuxRamfs:
		return nil
	default:
		return fmt.Errorf(
			"configuration filesystem %#x is unsupported",
			uint64(stat.Type),
		)
	}
}
