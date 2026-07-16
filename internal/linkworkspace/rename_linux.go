//go:build linux

package linkworkspace

import "golang.org/x/sys/unix"

func renameNoReplace(oldFD int, oldName string, newFD int, newName string) error {
	return unix.Renameat2(oldFD, oldName, newFD, newName, unix.RENAME_NOREPLACE)
}
