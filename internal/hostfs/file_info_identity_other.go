//go:build !darwin && !linux

package hostfs

import (
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func linkIdentityFromFileInfo(fs.FileInfo) domain.LinkIdentity {
	return domain.LinkIdentity{}
}
