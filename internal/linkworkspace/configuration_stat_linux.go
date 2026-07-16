//go:build linux

package linkworkspace

import "golang.org/x/sys/unix"

func sameConfigurationStat(left, right unix.Stat_t) bool {
	return left.Dev == right.Dev &&
		left.Ino == right.Ino &&
		left.Mode == right.Mode &&
		left.Uid == right.Uid &&
		left.Nlink == right.Nlink &&
		left.Size == right.Size &&
		left.Mtim == right.Mtim &&
		left.Ctim == right.Ctim
}
