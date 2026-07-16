//go:build darwin

package hostfs

import "golang.org/x/sys/unix"

func sameFileTimes(expected, opened unix.Stat_t) bool {
	return expected.Mtim == opened.Mtim &&
		expected.Ctim == opened.Ctim
}
