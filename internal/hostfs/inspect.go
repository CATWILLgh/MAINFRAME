package hostfs

import (
	"crypto/sha256"
	"encoding/hex"
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
	SHA256            string
	Mode              uint32
	Device            uint64
	Inode             uint64
	BirthSeconds      int64
	BirthNanoseconds  int64
}

func (namespace Namespace) InspectDigest(
	location domain.Location,
) (Entry, error) {
	entry, err := namespace.Inspect(location, true)
	if err != nil || entry.Kind != EntryRegular {
		return entry, err
	}
	sum := sha256.Sum256(entry.Content)
	entry.SHA256 = hex.EncodeToString(sum[:])
	entry.Content = nil
	return entry, nil
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
