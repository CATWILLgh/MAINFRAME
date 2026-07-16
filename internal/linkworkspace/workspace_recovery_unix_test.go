//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func TestInstallLifecycleIsIdempotentBeforeAndAfterPublication(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	before := fixture.inspect(t, location)
	private := fixture.preparePrivate(t, location)
	target := fixture.resolveSource(t, "bin/mainframe")
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationInstall, Location: location,
		SourceTarget: target, Before: image(before),
		After:  executor.LinkImage{Exists: true, RawTarget: target},
		Parent: before.Parent, Private: private, StagedName: "staged",
	}
	staged, err := fixture.workspace.StageInstall(mutation)
	if err != nil {
		t.Fatalf("first StageInstall() error = %v", err)
	}
	mutation.StagedIdentity = staged
	if repeated, err := fixture.workspace.StageInstall(mutation); err != nil || repeated != staged {
		t.Fatalf("repeated StageInstall() = %#v, %v", repeated, err)
	}
	published, err := fixture.workspace.PublishInstall(mutation)
	if err != nil || published.Entry != staged {
		t.Fatalf("first PublishInstall() = %#v, %v", published, err)
	}
	mutation.After.Entry = staged
	if repeated, err := fixture.workspace.PublishInstall(mutation); err != nil ||
		repeated.Entry != staged {
		t.Fatalf("repeated PublishInstall() = %#v, %v", repeated, err)
	}
	if err := fixture.workspace.Rollback(mutation); err != nil {
		t.Fatalf("first Rollback() error = %v", err)
	}
	if err := fixture.workspace.Rollback(mutation); err != nil {
		t.Fatalf("repeated Rollback() error = %v", err)
	}
	if err := fixture.workspace.Finalize(mutation); err != nil {
		t.Fatalf("first Finalize() error = %v", err)
	}
	if err := fixture.workspace.Finalize(mutation); err != nil {
		t.Fatalf("repeated Finalize() error = %v", err)
	}
	if err := fixture.workspace.FinalizePrivate(mutation); err != nil {
		t.Fatalf("first FinalizePrivate() error = %v", err)
	}
	if err := fixture.workspace.FinalizePrivate(mutation); err != nil {
		t.Fatalf("repeated FinalizePrivate() error = %v", err)
	}
}

func TestPublishRejectsChangedTargetParentIdentity(t *testing.T) {
	source := canonicalTempDir(t)
	target := canonicalTempDir(t)
	if err := os.MkdirAll(filepath.Join(source, "bin"), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	if err := os.WriteFile(filepath.Join(source, "bin", "mainframe"), nil, 0o755); err != nil {
		t.Fatalf("write source: %v", err)
	}
	parentPath := filepath.Join(target, "nested")
	if err := os.Mkdir(parentPath, 0o755); err != nil {
		t.Fatalf("mkdir target parent: %v", err)
	}
	workspace, err := New(source, map[domain.RootID]string{domain.RootUserBin: target})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	location := domain.Location{Root: domain.RootUserBin, Path: "nested/mainframe"}
	before, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	private := preparePrivateForTest(t, workspace, location)
	mutation := stagedMutationForTest(t, workspace, location, before, private)
	if err := os.Rename(parentPath, parentPath+"-old"); err != nil {
		t.Fatalf("rename target parent: %v", err)
	}
	if err := os.Mkdir(parentPath, 0o755); err != nil {
		t.Fatalf("replace target parent: %v", err)
	}
	if _, err := workspace.PublishInstall(mutation); err == nil {
		t.Fatal("PublishInstall() accepted a replaced target parent")
	}
}

func TestPreparePrivateRejectsChangedTargetParentIdentity(t *testing.T) {
	source := canonicalTempDir(t)
	target := canonicalTempDir(t)
	parentPath := filepath.Join(target, "nested")
	if err := os.Mkdir(parentPath, 0o755); err != nil {
		t.Fatalf("mkdir target parent: %v", err)
	}
	workspace, err := New(source, map[domain.RootID]string{domain.RootUserBin: target})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	location := domain.Location{Root: domain.RootUserBin, Path: "nested/mainframe"}
	before, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	if err := os.Rename(parentPath, parentPath+"-old"); err != nil {
		t.Fatalf("rename target parent: %v", err)
	}
	if err := os.Mkdir(parentPath, 0o755); err != nil {
		t.Fatalf("replace target parent: %v", err)
	}
	private := executor.PrivateDirectory{Name: ".mainframe-00000000000000000000000000000000"}
	if _, err := workspace.PreparePrivate(executor.WorkspaceMutation{
		Location: location,
		Parent:   before.Parent,
		Private:  private,
	}); err == nil {
		t.Fatal("PreparePrivate() accepted a replaced target parent")
	}
	if _, err := os.Stat(filepath.Join(parentPath, private.Name)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("PreparePrivate() mutated the replacement parent: %v", err)
	}
}

func TestPreparePrivateRejectsUnsafeCollision(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	before := fixture.inspect(t, location)
	name, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	collision := filepath.Join(fixture.target, name)
	if err := os.Mkdir(collision, 0o755); err != nil {
		t.Fatalf("mkdir collision: %v", err)
	}
	if _, err := fixture.workspace.PreparePrivate(executor.WorkspaceMutation{
		Location: location,
		Parent:   before.Parent,
		Private:  executor.PrivateDirectory{Name: name},
	}); err == nil {
		t.Fatal("PreparePrivate() adopted an unsafe collision")
	}
}

func TestRenameNoReplacePreservesExistingDestination(t *testing.T) {
	directory := canonicalTempDir(t)
	if err := os.WriteFile(filepath.Join(directory, "source"), []byte("source"), 0o600); err != nil {
		t.Fatalf("write source: %v", err)
	}
	if err := os.WriteFile(filepath.Join(directory, "destination"), []byte("destination"), 0o600); err != nil {
		t.Fatalf("write destination: %v", err)
	}
	fd, err := unix.Open(directory, directoryOpenFlags, 0)
	if err != nil {
		t.Fatalf("open directory: %v", err)
	}
	defer unix.Close(fd)
	if err := renameNoReplace(fd, "source", fd, "destination"); err == nil {
		t.Fatal("renameNoReplace() replaced an existing destination")
	}
	for _, name := range []string{"source", "destination"} {
		if _, err := os.Stat(filepath.Join(directory, name)); err != nil {
			t.Fatalf("%s disappeared: %v", name, err)
		}
	}
	if err := renameNoReplace(fd, "source", fd, "published"); err != nil {
		t.Fatalf("renameNoReplace() to absent destination error = %v", err)
	}
	if _, err := os.Stat(filepath.Join(directory, "published")); err != nil {
		t.Fatalf("published entry missing: %v", err)
	}
	if _, err := os.Stat(filepath.Join(directory, "source")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("source remains after rename: %v", err)
	}
}

func preparePrivateForTest(
	t *testing.T,
	workspace Workspace,
	location domain.Location,
) executor.PrivateDirectory {
	t.Helper()
	name, err := workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	private := executor.PrivateDirectory{Name: name}
	before, err := workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	private.Identity, err = workspace.PreparePrivate(executor.WorkspaceMutation{
		Location: location,
		Parent:   before.Parent,
		Private:  private,
	})
	if err != nil {
		t.Fatalf("PreparePrivate() error = %v", err)
	}
	return private
}

func stagedMutationForTest(
	t *testing.T,
	workspace Workspace,
	location domain.Location,
	before executor.LinkState,
	private executor.PrivateDirectory,
) executor.WorkspaceMutation {
	t.Helper()
	target, err := workspace.ResolveSource("bin/mainframe")
	if err != nil {
		t.Fatalf("ResolveSource() error = %v", err)
	}
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationInstall, Location: location,
		SourceTarget: target, Before: image(before),
		After:  executor.LinkImage{Exists: true, RawTarget: target},
		Parent: before.Parent, Private: private, StagedName: "staged",
	}
	mutation.StagedIdentity, err = workspace.StageInstall(mutation)
	if err != nil {
		t.Fatalf("StageInstall() error = %v", err)
	}
	return mutation
}
