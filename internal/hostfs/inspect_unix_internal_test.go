//go:build darwin || linux

package hostfs

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/sys/unix"
)

func TestInspectRegularRejectsConcurrentReplacementWithoutBlocking(t *testing.T) {
	tests := map[string]func(string) error{
		"regular file": func(path string) error {
			return os.WriteFile(path, []byte("replacement"), 0o600)
		},
		"FIFO": func(path string) error {
			return unix.Mkfifo(path, 0o600)
		},
	}
	for name, replace := range tests {
		t.Run(name, func(t *testing.T) {
			directory := t.TempDir()
			path := filepath.Join(directory, "target")
			if err := os.WriteFile(path, []byte("original"), 0o600); err != nil {
				t.Fatal(err)
			}
			parent, err := unix.Open(
				directory,
				unix.O_RDONLY|unix.O_DIRECTORY|unix.O_CLOEXEC,
				0,
			)
			if err != nil {
				t.Fatal(err)
			}
			defer unix.Close(parent)
			var expected unix.Stat_t
			if err := unix.Fstatat(
				parent,
				"target",
				&expected,
				unix.AT_SYMLINK_NOFOLLOW,
			); err != nil {
				t.Fatal(err)
			}
			if err := os.Rename(path, filepath.Join(directory, "original")); err != nil {
				t.Fatal(err)
			}
			if err := replace(path); err != nil {
				t.Fatal(err)
			}

			_, err = inspectRegularNoFollow(parent, "target", true, expected)
			if err == nil || !strings.Contains(err.Error(), "changed while being inspected") {
				t.Fatalf("inspectRegularNoFollow() error = %v", err)
			}
		})
	}
}

func TestSameFileSnapshotDetectsContentMetadataChanges(t *testing.T) {
	base := unix.Stat_t{
		Dev: 1, Ino: 2, Mode: unix.S_IFREG | 0o600, Size: 10,
	}
	tests := map[string]func(*unix.Stat_t){
		"identity": func(value *unix.Stat_t) { value.Ino++ },
		"mode":     func(value *unix.Stat_t) { value.Mode = unix.S_IFREG | 0o400 },
		"size":     func(value *unix.Stat_t) { value.Size++ },
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			changed := base
			mutate(&changed)
			if sameFileSnapshot(base, changed) {
				t.Fatal("changed file metadata was accepted")
			}
		})
	}
	if !sameFileSnapshot(base, base) {
		t.Fatal("identical file metadata was rejected")
	}
}

func TestInspectSymlinkRejectsReplacementAfterTargetRead(t *testing.T) {
	directory := t.TempDir()
	parent, err := unix.Open(
		directory,
		unix.O_RDONLY|unix.O_DIRECTORY|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(parent)

	const name = "mcp_config.json"
	if err := unix.Symlinkat("canonical.json", parent, name); err != nil {
		t.Fatal(err)
	}
	var expected unix.Stat_t
	if err := unix.Fstatat(parent, name, &expected, unix.AT_SYMLINK_NOFOLLOW); err != nil {
		t.Fatal(err)
	}

	readAndReplace := func(parent int, name string, buffer []byte) (int, error) {
		count, err := unix.Readlinkat(parent, name, buffer)
		if err != nil {
			return 0, err
		}
		if err := unix.Unlinkat(parent, name, 0); err != nil {
			return 0, err
		}
		if err := unix.Symlinkat("foreign.json", parent, name); err != nil {
			return 0, err
		}
		return count, nil
	}

	_, err = inspectSymlinkWithReadlink(
		parent,
		name,
		filepath.Join(directory, name),
		expected,
		readAndReplace,
	)
	if err == nil || !strings.Contains(err.Error(), "changed while being inspected") {
		t.Fatalf("inspectSymlinkWithReadlink() error = %v", err)
	}
}
