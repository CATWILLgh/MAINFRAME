//go:build linux

package hostfs

import (
	"errors"
	"fmt"

	"golang.org/x/sys/unix"
)

func stableIdentityAt(
	parentFD int,
	name string,
	stat unix.Stat_t,
) (stableFileIdentity, error) {
	var extended unix.Statx_t
	if err := unix.Statx(
		parentFD,
		name,
		unix.AT_SYMLINK_NOFOLLOW,
		unix.STATX_INO|unix.STATX_BTIME,
		&extended,
	); err != nil {
		return stableFileIdentity{}, fmt.Errorf(
			"inspect stable file identity: %w",
			err,
		)
	}
	if extended.Mask&unix.STATX_BTIME == 0 {
		return stableFileIdentity{}, errors.New(
			"stable file identity is unsupported: statx birth time is unavailable",
		)
	}
	device := unix.Mkdev(extended.Dev_major, extended.Dev_minor)
	if device != uint64(stat.Dev) || extended.Ino != uint64(stat.Ino) {
		return stableFileIdentity{}, errors.New(
			"file identity changed during inspection",
		)
	}
	return stableFileIdentity{
		device:           device,
		inode:            extended.Ino,
		birthSeconds:     extended.Btime.Sec,
		birthNanoseconds: int64(extended.Btime.Nsec),
	}, nil
}
