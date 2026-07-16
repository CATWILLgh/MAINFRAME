//go:build darwin

package linkworkspace

import (
	"errors"
	"fmt"
	"strings"

	"golang.org/x/sys/unix"
)

func checkConfigurationFilesystem(fd int) error {
	var stat unix.Statfs_t
	if err := unix.Fstatfs(fd, &stat); err != nil {
		return fmt.Errorf("inspect configuration filesystem: %w", err)
	}
	if stat.Flags&unix.MNT_LOCAL == 0 {
		return errors.New("configuration filesystem is not local")
	}
	kind := strings.TrimRight(string(stat.Fstypename[:]), "\x00")
	switch kind {
	case "apfs", "hfs":
		return nil
	default:
		return fmt.Errorf("configuration filesystem %q is unsupported", kind)
	}
}
