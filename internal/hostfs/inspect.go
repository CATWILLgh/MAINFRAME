package hostfs

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type EntryKind string

const (
	EntryRegular   EntryKind = "regular"
	EntryDirectory EntryKind = "directory"
	EntrySymlink   EntryKind = "symlink"
	EntryOther     EntryKind = "other"
)

type Entry struct {
	Kind              EntryKind
	Path              string
	SymlinkTargetPath string
	Content           []byte
	Mode              uint32
	Device            uint64
	Inode             uint64
}

func (namespace Namespace) Inspect(location domain.Location, includeContent bool) (Entry, error) {
	root, exists := namespace.roots.Targets[location.Root]
	if !exists {
		return Entry{}, fmt.Errorf("unknown root %q", location.Root)
	}
	if !location.Root.Valid() || !location.Path.Portable() {
		return Entry{}, fmt.Errorf("invalid configuration location %#v", location)
	}
	return inspectNoFollow(string(root), string(location.Path), includeContent)
}
