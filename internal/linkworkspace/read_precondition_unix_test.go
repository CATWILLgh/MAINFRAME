//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"golang.org/x/sys/unix"
)

func TestCheckReadPreconditionAcceptsExactRelativeSymlink(t *testing.T) {
	fixture := newConfigurationFixture(t, "legacy.json", nil, 0)
	canonical := filepath.Join(fixture.target, "canonical.json")
	if err := os.WriteFile(canonical, []byte("{}"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("canonical.json", fixture.publicPath()); err != nil {
		t.Fatal(err)
	}
	precondition := symlinkReadPrecondition(t, fixture, canonical)

	if err := fixture.workspace.CheckReadPrecondition(precondition); err != nil {
		t.Fatalf("CheckReadPrecondition() error = %v", err)
	}
}

func TestCheckReadPreconditionRejectsChangedSymlink(t *testing.T) {
	tests := []struct {
		name   string
		change func(*testing.T, configurationTestFixture)
	}{
		{
			name: "inode",
			change: func(t *testing.T, fixture configurationTestFixture) {
				t.Helper()
				if err := os.Remove(fixture.publicPath()); err != nil {
					t.Fatal(err)
				}
				if err := os.Symlink("canonical.json", fixture.publicPath()); err != nil {
					t.Fatal(err)
				}
			},
		},
		{
			name: "target",
			change: func(t *testing.T, fixture configurationTestFixture) {
				t.Helper()
				if err := os.Remove(fixture.publicPath()); err != nil {
					t.Fatal(err)
				}
				if err := os.Symlink("other.json", fixture.publicPath()); err != nil {
					t.Fatal(err)
				}
			},
		},
		{
			name: "type",
			change: func(t *testing.T, fixture configurationTestFixture) {
				t.Helper()
				if err := os.Remove(fixture.publicPath()); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(fixture.publicPath(), []byte("{}"), 0o600); err != nil {
					t.Fatal(err)
				}
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newConfigurationFixture(t, "legacy.json", nil, 0)
			canonical := filepath.Join(fixture.target, "canonical.json")
			if err := os.Symlink("canonical.json", fixture.publicPath()); err != nil {
				t.Fatal(err)
			}
			precondition := symlinkReadPrecondition(t, fixture, canonical)
			test.change(t, fixture)

			if err := fixture.workspace.CheckReadPrecondition(precondition); err == nil {
				t.Fatal("CheckReadPrecondition() accepted changed symlink")
			}
		})
	}
}

func TestCheckReadPreconditionRejectsUnexpectedImmediateTarget(t *testing.T) {
	fixture := newConfigurationFixture(t, "legacy.json", nil, 0)
	canonical := filepath.Join(fixture.target, "canonical.json")
	if err := os.Symlink("canonical.json", fixture.publicPath()); err != nil {
		t.Fatal(err)
	}
	precondition := symlinkReadPrecondition(t, fixture, canonical)
	precondition.ExpectedTargetPath = filepath.Join(fixture.target, "other.json")

	if err := fixture.workspace.CheckReadPrecondition(precondition); err == nil {
		t.Fatal("CheckReadPrecondition() accepted an unexpected immediate target")
	}
}

func TestCheckReadPreconditionRejectsSymlinkAncestor(t *testing.T) {
	base := newConfigurationFixture(t, "unused.json", nil, 0)
	real := filepath.Join(base.target, "real")
	if err := os.Mkdir(real, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("real", filepath.Join(base.target, "alias")); err != nil {
		t.Fatal(err)
	}
	fixture := configurationTestFixture{
		workspace: base.workspace,
		location: domain.Location{
			Root: base.location.Root,
			Path: "alias/legacy.json",
		},
		target: base.target,
	}
	link := filepath.Join(real, "legacy.json")
	if err := os.Symlink("../canonical.json", link); err != nil {
		t.Fatal(err)
	}
	info, err := os.Lstat(link)
	if err != nil {
		t.Fatal(err)
	}
	stat := info.Sys().(*syscall.Stat_t)
	precondition := configuration.ReadPrecondition{
		Kind:               configuration.ReadPreconditionSymlink,
		Target:             fixture.location,
		Device:             uint64(stat.Dev),
		Inode:              uint64(stat.Ino),
		ExpectedTargetPath: filepath.Join(base.target, "canonical.json"),
	}

	if err := fixture.workspace.CheckReadPrecondition(precondition); err == nil {
		t.Fatal("CheckReadPrecondition() followed a symbolic-link ancestor")
	}
}

func symlinkReadPrecondition(
	t *testing.T,
	fixture configurationTestFixture,
	expected string,
) configuration.ReadPrecondition {
	t.Helper()
	parentFD, name, _, err := fixture.workspace.openLocationParent(fixture.location)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(parentFD)
	identity, _, err := identityAt(parentFD, name)
	if err != nil {
		t.Fatal(err)
	}
	return configuration.ReadPrecondition{
		Kind:               configuration.ReadPreconditionSymlink,
		Target:             fixture.location,
		Device:             identity.Device,
		Inode:              identity.Inode,
		BirthSeconds:       identity.BirthSeconds,
		BirthNanoseconds:   identity.BirthNanoseconds,
		ExpectedTargetPath: expected,
	}
}
