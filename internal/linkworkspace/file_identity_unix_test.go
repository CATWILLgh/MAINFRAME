//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/sys/unix"
)

func TestStableIdentitySurvivesDirectoryContentChanges(t *testing.T) {
	root := t.TempDir()
	child := filepath.Join(root, "managed")
	if err := os.Mkdir(child, 0o700); err != nil {
		t.Fatal(err)
	}
	rootFD, err := unix.Open(root, directoryOpenFlags, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(rootFD)

	before, _, err := identityAt(rootFD, "managed")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(child, "payload"), []byte("value"), 0o600); err != nil {
		t.Fatal(err)
	}
	after, _, err := identityAt(rootFD, "managed")
	if err != nil {
		t.Fatal(err)
	}
	if after != before {
		t.Fatalf("directory identity changed after child creation: %#v != %#v", after, before)
	}
}

func TestStableIdentitySurvivesRename(t *testing.T) {
	root := t.TempDir()
	if err := os.Symlink("target", filepath.Join(root, "before")); err != nil {
		t.Fatal(err)
	}
	rootFD, err := unix.Open(root, directoryOpenFlags, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(rootFD)

	before, _, err := identityAt(rootFD, "before")
	if err != nil {
		t.Fatal(err)
	}
	if err := unix.Renameat(rootFD, "before", rootFD, "after"); err != nil {
		t.Fatal(err)
	}
	after, _, err := identityAt(rootFD, "after")
	if err != nil {
		t.Fatal(err)
	}
	if after != before {
		t.Fatalf("identity changed after rename: %#v != %#v", after, before)
	}
}

func TestStableIdentityRejectsRecreatedEntry(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "entry")
	if err := os.Symlink("target", path); err != nil {
		t.Fatal(err)
	}
	rootFD, err := unix.Open(root, directoryOpenFlags, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(rootFD)

	before, _, err := identityAt(rootFD, "entry")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("target", path); err != nil {
		t.Fatal(err)
	}
	after, _, err := identityAt(rootFD, "entry")
	if err != nil {
		t.Fatal(err)
	}
	if after == before {
		t.Fatalf("recreated entry retained the complete identity: %#v", after)
	}
}
