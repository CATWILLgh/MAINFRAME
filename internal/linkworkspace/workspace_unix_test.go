//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestInstallPublishesExactStagedLinkAndFinalizesPrivateDirectory(t *testing.T) {
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
		Phase: executor.StepPrepared,
	}

	staged, err := fixture.workspace.StageInstall(mutation)
	if err != nil {
		t.Fatalf("StageInstall() error = %v", err)
	}
	mutation.StagedIdentity = staged
	mutation.After.Entry = staged
	mutation.Phase = executor.StepStaged
	published, err := fixture.workspace.PublishInstall(mutation)
	if err != nil {
		t.Fatalf("PublishInstall() error = %v", err)
	}
	if !published.Exists || published.RawTarget != target || published.Entry != staged {
		t.Fatalf("published state = %#v", published)
	}
	mutation.Phase = executor.StepPublished
	if err := fixture.workspace.Finalize(mutation); err != nil {
		t.Fatalf("Finalize() error = %v", err)
	}
	if err := fixture.workspace.FinalizePrivate(mutation); err != nil {
		t.Fatalf("FinalizePrivate() error = %v", err)
	}
	if _, err := os.Lstat(filepath.Join(fixture.target, private.Name)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("private directory remains: %v", err)
	}
}

func TestInstallRollbackNeverUnlinksPublicName(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	before := fixture.inspect(t, location)
	private := fixture.preparePrivate(t, location)
	target := fixture.resolveSource(t, "bin/mainframe")
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationInstall, Location: location,
		SourceTarget: target, Before: image(before),
		After:  executor.LinkImage{Exists: true, RawTarget: target},
		Parent: before.Parent, Private: private,
		StagedName: "staged", RetainedName: "retained",
		Phase: executor.StepPrepared,
	}
	staged, err := fixture.workspace.StageInstall(mutation)
	if err != nil {
		t.Fatalf("StageInstall() error = %v", err)
	}
	mutation.StagedIdentity = staged
	mutation.After.Entry = staged
	mutation.Phase = executor.StepStaged
	if _, err := fixture.workspace.PublishInstall(mutation); err != nil {
		t.Fatalf("PublishInstall() error = %v", err)
	}
	mutation.Phase = executor.StepPublished

	if err := fixture.workspace.Rollback(mutation); err != nil {
		t.Fatalf("Rollback() error = %v", err)
	}
	if state := fixture.inspect(t, location); state.Exists {
		t.Fatalf("public link remains after rollback: %#v", state)
	}
	retained := filepath.Join(fixture.target, private.Name, mutation.RetainedName)
	if info, err := os.Lstat(retained); err != nil || info.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("rollback did not retain the link privately: info=%v error=%v", info, err)
	}
	if err := fixture.workspace.Finalize(mutation); err != nil {
		t.Fatalf("Finalize() error = %v", err)
	}
	if err := fixture.workspace.FinalizePrivate(mutation); err != nil {
		t.Fatalf("FinalizePrivate() error = %v", err)
	}
}

func TestRemoveRetainsAndRollbackRestoresExactLink(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	target := fixture.resolveSource(t, "bin/mainframe")
	public := filepath.Join(fixture.target, "mainframe")
	if err := os.Symlink(target, public); err != nil {
		t.Fatalf("create public link: %v", err)
	}
	before := fixture.inspect(t, location)
	private := fixture.preparePrivate(t, location)
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationRemove, Location: location,
		SourceTarget: target, Before: image(before), After: executor.LinkImage{},
		Parent: before.Parent, Private: private, RetainedName: "retained",
		Phase: executor.StepPrepared,
	}

	removed, err := fixture.workspace.PublishRemove(mutation)
	if err != nil {
		t.Fatalf("PublishRemove() error = %v", err)
	}
	if removed.Exists {
		t.Fatalf("removed state = %#v", removed)
	}
	mutation.Phase = executor.StepPublished
	if err := fixture.workspace.Rollback(mutation); err != nil {
		t.Fatalf("Rollback() error = %v", err)
	}
	restored := fixture.inspect(t, location)
	if !restored.Exists || restored.Entry != before.Entry || restored.RawTarget != target {
		t.Fatalf("restored state = %#v, before = %#v", restored, before)
	}
}

func TestRemoveFinalizeDeletesOnlyPrivateRetainedLink(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	target := fixture.resolveSource(t, "bin/mainframe")
	if err := os.Symlink(target, filepath.Join(fixture.target, "mainframe")); err != nil {
		t.Fatalf("create public link: %v", err)
	}
	before := fixture.inspect(t, location)
	private := fixture.preparePrivate(t, location)
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationRemove, Location: location,
		SourceTarget: target, Before: image(before), Parent: before.Parent,
		Private: private, RetainedName: "retained", Phase: executor.StepPrepared,
	}
	if _, err := fixture.workspace.PublishRemove(mutation); err != nil {
		t.Fatalf("PublishRemove() error = %v", err)
	}
	mutation.Phase = executor.StepPublished
	if err := fixture.workspace.Finalize(mutation); err != nil {
		t.Fatalf("Finalize() error = %v", err)
	}
	if err := fixture.workspace.FinalizePrivate(mutation); err != nil {
		t.Fatalf("FinalizePrivate() error = %v", err)
	}
	if _, err := os.Lstat(filepath.Join(fixture.target, "mainframe")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("public target reappeared: %v", err)
	}
}

func TestPublishInstallRejectsDestinationThatAppeared(t *testing.T) {
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
		t.Fatalf("StageInstall() error = %v", err)
	}
	mutation.StagedIdentity = staged
	mutation.After.Entry = staged
	mutation.Phase = executor.StepStaged
	if err := os.Symlink("foreign", filepath.Join(fixture.target, "mainframe")); err != nil {
		t.Fatalf("create competing link: %v", err)
	}
	if _, err := fixture.workspace.PublishInstall(mutation); err == nil {
		t.Fatal("PublishInstall() replaced a competing public link")
	}
	raw, err := os.Readlink(filepath.Join(fixture.target, "mainframe"))
	if err != nil || raw != "foreign" {
		t.Fatalf("competing public link changed: target=%q error=%v", raw, err)
	}
}

func TestPublishRemoveRejectsSameTargetWithDifferentInode(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	target := fixture.resolveSource(t, "bin/mainframe")
	public := filepath.Join(fixture.target, "mainframe")
	if err := os.Symlink(target, public); err != nil {
		t.Fatalf("create public link: %v", err)
	}
	before := fixture.inspect(t, location)
	private := fixture.preparePrivate(t, location)
	if err := os.Remove(public); err != nil {
		t.Fatalf("replace public link: %v", err)
	}
	if err := os.Symlink(target, public); err != nil {
		t.Fatalf("recreate public link: %v", err)
	}
	mutation := executor.WorkspaceMutation{
		Kind: executor.MutationRemove, Location: location,
		SourceTarget: target, Before: image(before), Parent: before.Parent,
		Private: private, RetainedName: "retained",
	}
	if _, err := fixture.workspace.PublishRemove(mutation); err == nil {
		t.Fatal("PublishRemove() moved a substituted public link")
	}
	if _, err := os.Lstat(public); err != nil {
		t.Fatalf("substituted public link was removed: %v", err)
	}
}

func TestWorkspaceRejectsMissingParentAndSymlinkAncestor(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	if _, err := fixture.workspace.Inspect(fixture.location("missing/mainframe")); err == nil {
		t.Fatal("Inspect() accepted a missing parent")
	}
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(fixture.target, "linked")); err != nil {
		t.Fatalf("create ancestor link: %v", err)
	}
	if _, err := fixture.workspace.Inspect(fixture.location("linked/mainframe")); err == nil {
		t.Fatal("Inspect() followed a symbolic-link ancestor")
	}
}

func TestAllocatePrivateNameIsPortableAndUnique(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	first, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("first AllocatePrivateName() error = %v", err)
	}
	second, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("second AllocatePrivateName() error = %v", err)
	}
	if first == second || !strings.HasPrefix(first, ".mainframe-") ||
		strings.ContainsAny(first, `/\`) {
		t.Fatalf("private names = %q, %q", first, second)
	}
}

type workspaceFixture struct {
	workspace Workspace
	source    string
	target    string
}

func newWorkspaceFixture(t *testing.T) workspaceFixture {
	t.Helper()
	source := canonicalTempDir(t)
	target := canonicalTempDir(t)
	if err := os.MkdirAll(filepath.Join(source, "bin"), 0o755); err != nil {
		t.Fatalf("mkdir source bin: %v", err)
	}
	if err := os.WriteFile(filepath.Join(source, "bin", "mainframe"), []byte("binary"), 0o755); err != nil {
		t.Fatalf("write source binary: %v", err)
	}
	workspace, err := New(source, map[domain.RootID]string{domain.RootUserBin: target})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	return workspaceFixture{workspace: workspace, source: source, target: target}
}

func (fixture workspaceFixture) location(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootUserBin, Path: path}
}

func (fixture workspaceFixture) inspect(t *testing.T, location domain.Location) executor.LinkState {
	t.Helper()
	state, err := fixture.workspace.Inspect(location)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	return state
}

func (fixture workspaceFixture) resolveSource(t *testing.T, source domain.ArtifactPath) string {
	t.Helper()
	target, err := fixture.workspace.ResolveSource(source)
	if err != nil {
		t.Fatalf("ResolveSource() error = %v", err)
	}
	return target
}

func (fixture workspaceFixture) preparePrivate(
	t *testing.T,
	location domain.Location,
) executor.PrivateDirectory {
	t.Helper()
	name, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	private := executor.PrivateDirectory{Name: name}
	before := fixture.inspect(t, location)
	private.Identity, err = fixture.workspace.PreparePrivate(executor.WorkspaceMutation{
		Location: location,
		Parent:   before.Parent,
		Private:  private,
	})
	if err != nil {
		t.Fatalf("PreparePrivate() error = %v", err)
	}
	return private
}

func image(state executor.LinkState) executor.LinkImage {
	return executor.LinkImage{
		Exists: state.Exists, RawTarget: state.RawTarget, Entry: state.Entry,
	}
}

func canonicalTempDir(t *testing.T) string {
	t.Helper()
	path, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("resolve temp directory: %v", err)
	}
	return path
}
