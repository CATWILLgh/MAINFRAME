//go:build darwin || linux

package hostfs

import (
	"io/fs"
	"syscall"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func linkIdentityFromFileInfo(info fs.FileInfo) domain.LinkIdentity {
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return domain.LinkIdentity{}
	}
	return domain.LinkIdentity{
		Device: uint64(stat.Dev),
		Inode:  uint64(stat.Ino),
	}
}
