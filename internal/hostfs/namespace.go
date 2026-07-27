package hostfs

import (
	"fmt"
	"io/fs"
	"os"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
)

type Namespace struct {
	filesystem fs.ReadLinkFS
	roots      discovery.Roots
}

type namespaceFilesystem struct {
	fs.ReadLinkFS
}

func Open(layout hostlayout.Layout) (Namespace, error) {
	filesystem, ok := os.DirFS("/").(fs.ReadLinkFS)
	if !ok {
		return Namespace{}, fmt.Errorf("host filesystem does not support reading symbolic links")
	}
	source, err := canonicalFSPath("source", layout.Source())
	if err != nil {
		return Namespace{}, err
	}
	targets, err := canonicalTargets(layout.Targets())
	if err != nil {
		return Namespace{}, err
	}
	return Namespace{
		filesystem: namespaceFilesystem{ReadLinkFS: filesystem},
		roots: discovery.Roots{
			Source:  source,
			Targets: targets,
		},
	}, nil
}

func (filesystem namespaceFilesystem) StableLinkIdentity(
	name string,
	info fs.FileInfo,
) (domain.LinkIdentity, error) {
	entry, err := inspectNoFollow("/", name, false)
	if err != nil {
		return domain.LinkIdentity{}, err
	}
	observed := linkIdentityFromFileInfo(info)
	if observed.Device != entry.Device || observed.Inode != entry.Inode {
		return domain.LinkIdentity{}, fmt.Errorf("link identity changed during discovery")
	}
	return domain.LinkIdentity{
		Device:           entry.Device,
		Inode:            entry.Inode,
		BirthSeconds:     entry.BirthSeconds,
		BirthNanoseconds: entry.BirthNanoseconds,
	}, nil
}

func (namespace Namespace) Filesystem() fs.ReadLinkFS {
	return namespace.filesystem
}

func (namespace Namespace) Roots() discovery.Roots {
	targets := make(map[domain.RootID]domain.ArtifactPath, len(namespace.roots.Targets))
	for root, target := range namespace.roots.Targets {
		targets[root] = target
	}
	return discovery.Roots{Source: namespace.roots.Source, Targets: targets}
}

func canonicalTargets(targets map[domain.RootID]string) (map[domain.RootID]domain.ArtifactPath, error) {
	roots := make([]domain.RootID, 0, len(targets))
	for root := range targets {
		roots = append(roots, root)
	}
	sort.Slice(roots, func(i, j int) bool { return roots[i] < roots[j] })
	canonical := make(map[domain.RootID]domain.ArtifactPath, len(targets))
	for _, root := range roots {
		target, err := canonicalFSPath(fmt.Sprintf("target root %q", root), targets[root])
		if err != nil {
			return nil, err
		}
		canonical[root] = target
	}
	return canonical, nil
}
