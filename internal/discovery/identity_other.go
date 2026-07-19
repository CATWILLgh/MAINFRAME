//go:build !unix

package discovery

import (
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func linkIdentity(fs.FileInfo) domain.LinkIdentity {
	return domain.LinkIdentity{}
}
