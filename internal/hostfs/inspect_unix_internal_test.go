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
			parent, err := unix.Open(directory, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_CLOEXEC, 0)
			if err != nil {
				t.Fatal(err)
			}
			defer unix.Close(parent)
			var expected unix.Stat_t
			if err := unix.Fstatat(parent, "target", &expected, unix.AT_SYMLINK_NOFOLLOW); err != nil {
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
