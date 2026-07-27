//go:build linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func identityFromFD(fd int, stat unix.Stat_t) (executor.FileIdentity, error) {
	return linuxBirthIdentity(fd, "", unix.AT_EMPTY_PATH, stat)
}

func identityFromName(
	parentFD int,
	name string,
	stat unix.Stat_t,
) (executor.FileIdentity, error) {
	return linuxBirthIdentity(parentFD, name, unix.AT_SYMLINK_NOFOLLOW, stat)
}

func linuxBirthIdentity(
	parentFD int,
	name string,
	flags int,
	stat unix.Stat_t,
) (executor.FileIdentity, error) {
	var extended unix.Statx_t
	if err := unix.Statx(
		parentFD,
		name,
		flags,
		unix.STATX_INO|unix.STATX_BTIME,
		&extended,
	); err != nil {
		return executor.FileIdentity{}, fmt.Errorf(
			"inspect stable file identity: %w",
			err,
		)
	}
	return linuxIdentityFromStats(stat, extended)
}

func linuxIdentityFromStats(
	stat unix.Stat_t,
	extended unix.Statx_t,
) (executor.FileIdentity, error) {
	if extended.Mask&unix.STATX_BTIME == 0 {
		return executor.FileIdentity{}, errors.New(
			"stable file identity is unsupported: statx birth time is unavailable",
		)
	}
	device := unix.Mkdev(extended.Dev_major, extended.Dev_minor)
	if device != uint64(stat.Dev) || extended.Ino != uint64(stat.Ino) {
		return executor.FileIdentity{}, errors.New(
			"file identity changed during inspection",
		)
	}
	return executor.FileIdentity{
		Device:           device,
		Inode:            extended.Ino,
		BirthSeconds:     extended.Btime.Sec,
		BirthNanoseconds: int64(extended.Btime.Nsec),
	}, nil
}
