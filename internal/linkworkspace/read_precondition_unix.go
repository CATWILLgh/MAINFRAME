//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func (workspace Workspace) CheckReadPrecondition(
	precondition configuration.ReadPrecondition,
) error {
	if precondition.Kind != configuration.ReadPreconditionSymlink {
		return errors.New("unsupported read precondition")
	}
	parentFD, name, parent, err := workspace.openLocationParent(precondition.Target)
	if err != nil {
		return fmt.Errorf("open read precondition target: %w", err)
	}
	defer unix.Close(parentFD)
	before, beforeMode, err := identityAt(parentFD, name)
	if err != nil {
		return fmt.Errorf("inspect read precondition target: %w", err)
	}
	expected := executor.FileIdentity{
		Device:           precondition.Device,
		Inode:            precondition.Inode,
		BirthSeconds:     precondition.BirthSeconds,
		BirthNanoseconds: precondition.BirthNanoseconds,
	}
	if fileType(beforeMode) != unix.S_IFLNK || before != expected {
		return errors.New("read precondition target changed")
	}
	rawTarget, err := readLinkAt(parentFD, name)
	if err != nil {
		return fmt.Errorf("read precondition target: %w", err)
	}
	after, afterMode, err := identityAt(parentFD, name)
	if err != nil || after != before || afterMode != beforeMode {
		return errors.New("read precondition target changed during inspection")
	}
	actual, err := workspace.normalizeImmediateTarget(precondition, rawTarget)
	if err != nil {
		return err
	}
	if actual != precondition.ExpectedTargetPath {
		return errors.New("read precondition symlink target changed")
	}
	return workspace.confirmReadPreconditionParent(precondition, parent)
}

func (workspace Workspace) confirmReadPreconditionParent(
	precondition configuration.ReadPrecondition,
	expected executor.FileIdentity,
) error {
	parentFD, _, actual, err := workspace.openLocationParent(precondition.Target)
	if err != nil {
		return fmt.Errorf("reopen read precondition target: %w", err)
	}
	defer unix.Close(parentFD)
	if actual != expected {
		return errors.New("read precondition parent changed during inspection")
	}
	return nil
}

func (workspace Workspace) normalizeImmediateTarget(
	precondition configuration.ReadPrecondition,
	rawTarget string,
) (string, error) {
	if rawTarget == "" {
		return "", errors.New("read precondition symlink target is empty")
	}
	if filepath.IsAbs(rawTarget) {
		return filepath.Clean(rawTarget), nil
	}
	root, found, err := workspace.target(precondition.Target.Root)
	if err != nil {
		return "", err
	}
	if !found {
		return "", fmt.Errorf("unknown target root %q", precondition.Target.Root)
	}
	parent := filepath.Dir(filepath.FromSlash(string(precondition.Target.Path)))
	return filepath.Clean(filepath.Join(root.absolute(), parent, rawTarget)), nil
}
