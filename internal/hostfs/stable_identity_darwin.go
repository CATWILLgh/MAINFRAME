//go:build darwin

package hostfs

import "golang.org/x/sys/unix"

func stableIdentityAt(
	_ int,
	_ string,
	stat unix.Stat_t,
) (stableFileIdentity, error) {
	return stableFileIdentity{
		device:           uint64(stat.Dev),
		inode:            uint64(stat.Ino),
		birthSeconds:     stat.Btim.Sec,
		birthNanoseconds: stat.Btim.Nsec,
	}, nil
}
