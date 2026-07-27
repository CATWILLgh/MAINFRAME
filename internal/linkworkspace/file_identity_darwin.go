//go:build darwin

package linkworkspace

import (
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func identityFromFD(_ int, stat unix.Stat_t) (executor.FileIdentity, error) {
	return identityFromStat(stat), nil
}

func identityFromName(_ int, _ string, stat unix.Stat_t) (executor.FileIdentity, error) {
	return identityFromStat(stat), nil
}

func identityFromStat(stat unix.Stat_t) executor.FileIdentity {
	return executor.FileIdentity{
		Device:           uint64(stat.Dev),
		Inode:            uint64(stat.Ino),
		BirthSeconds:     stat.Btim.Sec,
		BirthNanoseconds: stat.Btim.Nsec,
	}
}
