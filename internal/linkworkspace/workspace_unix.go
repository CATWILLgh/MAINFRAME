//go:build darwin || linux

package linkworkspace

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"path"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

const privateNamePrefix = ".mainframe-"

type Workspace struct {
	source  pinnedRoot
	targets map[domain.RootID]pinnedRoot
}

func New(source string, targets map[domain.RootID]string) (Workspace, error) {
	sourceRoot, err := pinRoot(source)
	if err != nil {
		return Workspace{}, fmt.Errorf("pin source root: %w", err)
	}
	pinnedTargets := make(map[domain.RootID]pinnedRoot, len(targets))
	for id, target := range targets {
		if !id.Valid() {
			return Workspace{}, fmt.Errorf("invalid target root %q", id)
		}
		root, pinErr := pinRoot(target)
		if pinErr != nil {
			return Workspace{}, fmt.Errorf("pin target root %q: %w", id, pinErr)
		}
		pinnedTargets[id] = root
	}
	return Workspace{source: sourceRoot, targets: pinnedTargets}, nil
}

func (workspace Workspace) Inspect(location domain.Location) (executor.LinkState, error) {
	parentFD, final, parent, err := workspace.openLocationParent(location)
	if err != nil {
		return executor.LinkState{}, err
	}
	defer unix.Close(parentFD)
	return inspectAt(parentFD, final, parent)
}

func (workspace Workspace) ResolveSource(source domain.ArtifactPath) (string, error) {
	if !source.Portable() {
		return "", errors.New("source path is not portable")
	}
	segments := strings.Split(string(source), "/")
	rootFD, err := workspace.source.open()
	if err != nil {
		return "", fmt.Errorf("open source root: %w", err)
	}
	defer unix.Close(rootFD)
	parentFD, err := openRelativeDirectory(rootFD, segments[:len(segments)-1])
	if err != nil {
		return "", fmt.Errorf("open source parent: %w", err)
	}
	defer unix.Close(parentFD)
	_, mode, err := identityAt(parentFD, segments[len(segments)-1])
	if err != nil {
		return "", fmt.Errorf("inspect source: %w", err)
	}
	if fileType(mode) == unix.S_IFLNK {
		return "", errors.New("source entry is a symbolic link")
	}
	return path.Join(workspace.source.path, string(source)), nil
}

func (workspace Workspace) AllocatePrivateName() (string, error) {
	random := make([]byte, 16)
	if _, err := rand.Read(random); err != nil {
		return "", fmt.Errorf("generate private name: %w", err)
	}
	return privateNamePrefix + hex.EncodeToString(random), nil
}

func (workspace Workspace) PreparePrivate(
	mutation executor.WorkspaceMutation,
) (executor.FileIdentity, error) {
	private := mutation.Private
	if !validPrivateName(private.Name) {
		return executor.FileIdentity{}, errors.New("invalid private directory name")
	}
	if !validFileIdentity(mutation.Parent) {
		return executor.FileIdentity{}, errors.New("invalid target parent identity")
	}
	parentFD, _, parent, err := workspace.openLocationParent(mutation.Location)
	if err != nil {
		return executor.FileIdentity{}, err
	}
	defer unix.Close(parentFD)
	if parent != mutation.Parent {
		return executor.FileIdentity{}, errors.New("target parent identity changed")
	}
	if private.Identity != (executor.FileIdentity{}) {
		identity, adoptErr := adoptPrivateDirectory(parentFD, private)
		return identity, errors.Join(adoptErr, workspace.verifyParentIdentity(mutation))
	}
	if err := unix.Mkdirat(parentFD, private.Name, 0o700); err != nil {
		if !errors.Is(err, unix.EEXIST) {
			return executor.FileIdentity{}, fmt.Errorf("create private directory: %w", err)
		}
		identity, adoptErr := adoptPrivateDirectory(parentFD, private)
		return identity, errors.Join(adoptErr, workspace.verifyParentIdentity(mutation))
	}
	if err := syncDirectory(parentFD); err != nil {
		return executor.FileIdentity{}, err
	}
	identity, _, err := identityAt(parentFD, private.Name)
	return identity, errors.Join(err, workspace.verifyParentIdentity(mutation))
}

func (workspace Workspace) openLocationParent(
	location domain.Location,
) (int, string, executor.FileIdentity, error) {
	if !location.Path.Portable() || !location.Root.Valid() {
		return -1, "", executor.FileIdentity{}, errors.New("location is not portable")
	}
	root, found := workspace.targets[location.Root]
	if !found {
		return -1, "", executor.FileIdentity{}, fmt.Errorf("unknown target root %q", location.Root)
	}
	segments := strings.Split(string(location.Path), "/")
	rootFD, err := root.open()
	if err != nil {
		return -1, "", executor.FileIdentity{}, fmt.Errorf("open target root: %w", err)
	}
	defer unix.Close(rootFD)
	parentFD, err := openRelativeDirectory(rootFD, segments[:len(segments)-1])
	if err != nil {
		return -1, "", executor.FileIdentity{}, fmt.Errorf("open target parent: %w", err)
	}
	identity, err := identityOfFD(parentFD)
	if err != nil {
		unix.Close(parentFD)
		return -1, "", executor.FileIdentity{}, fmt.Errorf("identify target parent: %w", err)
	}
	return parentFD, segments[len(segments)-1], identity, nil
}

func inspectAt(
	parentFD int,
	name string,
	parent executor.FileIdentity,
) (executor.LinkState, error) {
	identity, mode, err := identityAt(parentFD, name)
	if isMissing(err) {
		return executor.LinkState{Parent: parent}, nil
	}
	if err != nil {
		return executor.LinkState{}, fmt.Errorf("inspect target: %w", err)
	}
	if fileType(mode) != unix.S_IFLNK {
		return executor.LinkState{}, errors.New("target entry is not a symbolic link")
	}
	target, err := readLinkAt(parentFD, name)
	if err != nil {
		return executor.LinkState{}, fmt.Errorf("read target link: %w", err)
	}
	return executor.LinkState{
		Exists: true, RawTarget: target, Parent: parent, Entry: identity,
	}, nil
}

func adoptPrivateDirectory(
	parentFD int,
	private executor.PrivateDirectory,
) (executor.FileIdentity, error) {
	fd, identity, err := openPrivateAt(parentFD, private.Name, private.Identity)
	if err != nil {
		return executor.FileIdentity{}, fmt.Errorf("adopt private directory: %w", err)
	}
	defer unix.Close(fd)
	empty, err := directoryEmpty(fd)
	if err != nil {
		return executor.FileIdentity{}, err
	}
	if !empty {
		return executor.FileIdentity{}, errors.New("private directory is not empty")
	}
	return identity, nil
}

func validPrivateName(name string) bool {
	if !strings.HasPrefix(name, privateNamePrefix) {
		return false
	}
	suffix := strings.TrimPrefix(name, privateNamePrefix)
	if len(suffix) != 32 {
		return false
	}
	_, err := hex.DecodeString(suffix)
	return err == nil
}

func validEntryName(name string) bool {
	return name != "" && name != "." && name != ".." &&
		!strings.ContainsAny(name, `/\`) && domain.ArtifactPath(name).Portable()
}
