//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func openPrivateAt(
	parentFD int,
	name string,
	expected executor.FileIdentity,
) (int, executor.FileIdentity, error) {
	if !validPrivateName(name) {
		return -1, executor.FileIdentity{}, errors.New("invalid private directory name")
	}
	fd, err := unix.Openat(parentFD, name, directoryOpenFlags, 0)
	if err != nil {
		return -1, executor.FileIdentity{}, err
	}
	actual, err := identityOfFD(fd)
	if err != nil {
		unix.Close(fd)
		return -1, executor.FileIdentity{}, err
	}
	if expected != (executor.FileIdentity{}) && actual != expected {
		unix.Close(fd)
		return -1, executor.FileIdentity{}, errors.New("private directory identity changed")
	}
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		unix.Close(fd)
		return -1, executor.FileIdentity{}, err
	}
	if stat.Uid != uint32(os.Geteuid()) || stat.Mode&0o7777 != 0o700 {
		unix.Close(fd)
		return -1, executor.FileIdentity{}, errors.New("private directory ownership or mode differs")
	}
	return fd, actual, nil
}

func inspectPrivateLink(
	privateFD int,
	name string,
	expectedTarget string,
	expectedIdentity executor.FileIdentity,
) (executor.FileIdentity, bool, error) {
	if !validEntryName(name) {
		return executor.FileIdentity{}, false, errors.New("invalid private entry name")
	}
	identity, mode, err := identityAt(privateFD, name)
	if isMissing(err) {
		return executor.FileIdentity{}, false, nil
	}
	if err != nil {
		return executor.FileIdentity{}, false, err
	}
	if fileType(mode) != unix.S_IFLNK {
		return executor.FileIdentity{}, false, errors.New("private entry is not a symbolic link")
	}
	target, err := readLinkAt(privateFD, name)
	if err != nil {
		return executor.FileIdentity{}, false, err
	}
	if target != expectedTarget {
		return executor.FileIdentity{}, false, errors.New("private link target changed")
	}
	if expectedIdentity != (executor.FileIdentity{}) && identity != expectedIdentity {
		return executor.FileIdentity{}, false, errors.New("private link identity changed")
	}
	return identity, true, nil
}

func removeVerifiedPrivateLink(
	privateFD int,
	name string,
	target string,
	identity executor.FileIdentity,
) error {
	_, exists, err := inspectPrivateLink(privateFD, name, target, identity)
	if err != nil || !exists {
		return err
	}
	if err := unix.Unlinkat(privateFD, name, 0); err != nil {
		return fmt.Errorf("remove private link: %w", err)
	}
	return syncDirectory(privateFD)
}
