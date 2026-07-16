//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func (workspace Workspace) openDirectoryContext(
	mutation executor.DirectoryMutation,
) (directoryContext, error) {
	if err := validateDirectoryMutation(mutation); err != nil {
		return directoryContext{}, err
	}
	configured, exists := workspace.targets[mutation.Root.Root]
	if !exists || configured.absolute() != filepath.Clean(filepath.Join(
		mutation.Root.AnchorPath,
		filepath.FromSlash(mutation.Root.RootPath),
	)) {
		return directoryContext{}, errors.New(
			"managed directory root differs from workspace configuration",
		)
	}
	anchor := pinnedRoot{
		path:     mutation.Root.AnchorPath,
		identity: mutation.Root.AnchorIdentity,
	}
	anchorFD, err := anchor.open()
	if err != nil {
		return directoryContext{}, fmt.Errorf("open managed root anchor: %w", err)
	}
	segments := strings.Split(mutation.Target.Path, "/")
	parentFD, err := openRelativeDirectory(anchorFD, segments[:len(segments)-1])
	unix.Close(anchorFD)
	if err != nil {
		return directoryContext{}, fmt.Errorf("open managed directory parent: %w", err)
	}
	parent, err := identityOfFD(parentFD)
	if err != nil {
		unix.Close(parentFD)
		return directoryContext{}, fmt.Errorf("identify managed directory parent: %w", err)
	}
	if mutation.Parent != (executor.FileIdentity{}) && mutation.Parent != parent {
		unix.Close(parentFD)
		return directoryContext{}, errors.New("managed directory parent identity changed")
	}
	return directoryContext{
		parentFD: parentFD,
		final:    segments[len(segments)-1],
		parent:   parent,
	}, nil
}

func validateDirectoryMutation(mutation executor.DirectoryMutation) error {
	if mutation.Root.Root != mutation.Target.Root ||
		!mutation.Root.Root.Valid() ||
		!filepath.IsAbs(mutation.Root.AnchorPath) ||
		filepath.Clean(mutation.Root.AnchorPath) != mutation.Root.AnchorPath ||
		!validFileIdentity(mutation.Root.AnchorIdentity) ||
		!domain.ArtifactPath(mutation.Target.Path).Portable() ||
		mutation.Mode != executor.ManagedDirectoryMode ||
		!validPrivateName(mutation.PrivateName) {
		return errors.New("invalid managed directory mutation")
	}
	if mutation.Root.RootPath != "" &&
		mutation.Target.Path != mutation.Root.RootPath &&
		!strings.HasPrefix(mutation.Target.Path, mutation.Root.RootPath+"/") &&
		!strings.HasPrefix(mutation.Root.RootPath, mutation.Target.Path+"/") {
		return errors.New("managed directory target escapes its root")
	}
	return nil
}

func inspectDirectoryAt(
	parentFD int,
	name string,
	parent executor.FileIdentity,
) (executor.DirectoryState, error) {
	identity, mode, err := identityAt(parentFD, name)
	if isMissing(err) {
		return executor.DirectoryState{Parent: parent}, nil
	}
	if err != nil {
		return executor.DirectoryState{}, err
	}
	if fileType(mode) != unix.S_IFDIR {
		return executor.DirectoryState{}, errors.New("managed path is not a directory")
	}
	return executor.DirectoryState{
		Exists: true,
		Parent: parent,
		Entry:  identity,
		Mode:   mode & 0o7777,
	}, nil
}

func inspectPrivateDirectory(
	parentFD int,
	name string,
	expected executor.FileIdentity,
	mode uint32,
) (executor.FileIdentity, bool, error) {
	identity, exists, empty, err := inspectOwnedDirectory(
		parentFD,
		name,
		expected,
		mode,
	)
	if err != nil || !exists {
		return identity, exists, err
	}
	if !empty {
		return executor.FileIdentity{}, false, errors.New(
			"managed private directory is not empty",
		)
	}
	return identity, true, nil
}

func inspectOwnedDirectory(
	parentFD int,
	name string,
	expected executor.FileIdentity,
	mode uint32,
) (executor.FileIdentity, bool, bool, error) {
	fd, err := unix.Openat(parentFD, name, directoryOpenFlags, 0)
	if isMissing(err) {
		return executor.FileIdentity{}, false, false, nil
	}
	if err != nil {
		return executor.FileIdentity{}, false, false, err
	}
	defer unix.Close(fd)
	identity, err := identityOfFD(fd)
	if err != nil {
		return executor.FileIdentity{}, false, false, err
	}
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		return executor.FileIdentity{}, false, false, err
	}
	if expected != (executor.FileIdentity{}) && identity != expected {
		return executor.FileIdentity{}, false, false, errors.New(
			"managed directory identity changed",
		)
	}
	if stat.Uid != uint32(os.Geteuid()) || uint32(stat.Mode)&0o7777 != mode {
		return executor.FileIdentity{}, false, false, errors.New(
			"managed directory ownership or mode differs",
		)
	}
	empty, err := directoryEmpty(fd)
	if err != nil {
		return executor.FileIdentity{}, false, false, err
	}
	return identity, true, empty, nil
}

func exactDirectoryEmpty(
	parentFD int,
	name string,
	expected executor.FileIdentity,
	mode uint32,
) (bool, error) {
	_, exists, err := inspectPrivateDirectory(parentFD, name, expected, mode)
	return exists, err
}

func matchesDirectory(
	state executor.DirectoryState,
	mutation executor.DirectoryMutation,
) bool {
	return state.Exists &&
		state.Parent == mutation.Parent &&
		state.Entry == mutation.Entry &&
		state.Mode == mutation.Mode
}

func verifyDirectoryParent(
	context directoryContext,
	mutation executor.DirectoryMutation,
) error {
	actual, err := identityOfFD(context.parentFD)
	if err != nil {
		return err
	}
	if actual != mutation.Parent {
		return errors.New("managed directory parent identity changed")
	}
	return nil
}
