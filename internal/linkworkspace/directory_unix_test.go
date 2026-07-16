//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func TestManagedDirectoryPlanIsReadOnlyAndParentFirst(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, ".local", "bin")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	plan := installPlan(domain.RootUserBin, "nested/mainframe")

	directories, err := workspace.PlanDirectories(plan)

	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	var paths []string
	for _, requirement := range directories.Missing {
		paths = append(paths, requirement.Target.Path)
	}
	want := []string{".local", ".local/bin", ".local/bin/nested"}
	if !reflect.DeepEqual(paths, want) {
		t.Fatalf("missing directories = %#v, want %#v", paths, want)
	}
	if _, err := os.Lstat(filepath.Join(parent, ".local")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("planning created a directory: %v", err)
	}
}

func TestManagedDirectoryPlanPreservesExistingParentMode(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	existing := filepath.Join(parent, ".local")
	if err := os.Mkdir(existing, 0o755); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(existing, "bin")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	directories, err := workspace.PlanDirectories(
		installPlan(domain.RootUserBin, "nested/mainframe"),
	)

	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	var paths []string
	for _, requirement := range directories.Missing {
		paths = append(paths, requirement.Target.Path)
	}
	if want := []string{"bin", "bin/nested"}; !reflect.DeepEqual(paths, want) {
		t.Fatalf("missing directories = %#v, want %#v", paths, want)
	}
	info, err := os.Stat(existing)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o755 {
		t.Fatalf("existing parent mode = %#o", info.Mode().Perm())
	}
}

func TestManagedDirectoryModeCheckRejectsOwnerMask(t *testing.T) {
	previousMask := unix.Umask(0o700)
	defer unix.Umask(previousMask)
	workspace := Workspace{}

	err := workspace.CheckDirectoryMode(executor.ManagedDirectoryMode)

	if err == nil || !strings.Contains(err.Error(), "umask 0700") {
		t.Fatalf("CheckDirectoryMode() error = %v", err)
	}
	if observedMask := unix.Umask(0o700); observedMask != 0o700 {
		t.Fatalf("process umask changed to %#o", observedMask)
	}
	unix.Umask(0o077)
	if err := workspace.CheckDirectoryMode(executor.ManagedDirectoryMode); err != nil {
		t.Fatalf("CheckDirectoryMode() with 0077: %v", err)
	}
}

func TestManagedDirectoryInspectionRejectsSymlinkSubstitution(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, ".local", "bin")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	directoryPlan, err := workspace.PlanDirectories(
		installPlan(domain.RootUserBin, "mainframe"),
	)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(parent, ".local")); err != nil {
		t.Fatal(err)
	}
	requirement := directoryPlan.Missing[0]
	mutation := executor.DirectoryMutation{
		Root:        directoryPlan.Roots[0],
		Target:      requirement.Target,
		Mode:        requirement.Mode,
		PrivateName: ".mainframe-00000000000000000000000000000001",
		Phase:       executor.StepPrepared,
	}

	if _, err := workspace.InspectDirectory(mutation); err == nil {
		t.Fatal("InspectDirectory() followed a substituted symbolic link")
	}
	entries, err := os.ReadDir(outside)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("outside directory changed: %#v", entries)
	}
}

func TestManagedDirectoryLifecyclePublishesAndRollsBackExactInodes(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, ".local", "bin")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	directoryPlan, err := workspace.PlanDirectories(
		installPlan(domain.RootUserBin, "nested/mainframe"),
	)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	mutations := publishManagedDirectories(t, workspace, directoryPlan)
	for index := len(mutations) - 1; index >= 0; index-- {
		mutation := mutations[index]
		if err := workspace.RollbackDirectory(mutation); err != nil {
			t.Fatalf("RollbackDirectory() error = %v", err)
		}
		mutation.Phase = executor.StepRolledBack
		if err := workspace.FinalizeDirectory(mutation); err != nil {
			t.Fatalf("FinalizeDirectory() error = %v", err)
		}
	}
	if _, err := os.Lstat(filepath.Join(parent, ".local")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("managed directory remains after rollback: %v", err)
	}
}

func TestManagedDirectoryPublishDoesNotReplaceForeignDirectory(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, ".local")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	directoryPlan, err := workspace.PlanDirectories(
		installPlan(domain.RootUserBin, "mainframe"),
	)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	mutation := stageManagedDirectory(
		t,
		workspace,
		directoryPlan.Roots[0],
		directoryPlan.Missing[0],
	)
	if err := os.Mkdir(target, 0o700); err != nil {
		t.Fatalf("create foreign directory: %v", err)
	}
	foreign, err := os.Lstat(target)
	if err != nil {
		t.Fatal(err)
	}

	if _, err := workspace.PublishDirectory(mutation); err == nil {
		t.Fatal("PublishDirectory() replaced a foreign directory")
	}

	after, err := os.Lstat(target)
	if err != nil {
		t.Fatal(err)
	}
	if !os.SameFile(foreign, after) {
		t.Fatal("foreign directory identity changed")
	}
}

func TestManagedDirectoryRollbackRestoresDirectoryPopulatedDuringRename(t *testing.T) {
	parent := t.TempDir()
	source := t.TempDir()
	target := filepath.Join(parent, ".local")
	workspace, err := New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	directoryPlan, err := workspace.PlanDirectories(
		installPlan(domain.RootUserBin, "mainframe"),
	)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	mutation := publishManagedDirectory(
		t,
		workspace,
		directoryPlan.Roots[0],
		directoryPlan.Missing[0],
	)
	name := mutation.PrivateName
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		t.Fatalf("openDirectoryContext() error = %v", err)
	}
	err = rollbackPublishedDirectory(context, mutation, func() {
		populatePrivateAndOccupyPublic(t, parent, name, target)
	})
	context.close()

	if err == nil {
		t.Fatal("rollback accepted a directory populated during rename")
	}
	if _, statErr := os.Lstat(filepath.Join(parent, name, "concurrent")); statErr != nil {
		t.Fatalf("populated private directory was not retained: %v", statErr)
	}
	if removeErr := os.Remove(target); removeErr != nil {
		t.Fatalf("remove competing public directory: %v", removeErr)
	}
	if retryErr := workspace.RollbackDirectory(mutation); retryErr == nil {
		t.Fatal("retry hid the populated-directory conflict")
	}
	if content, readErr := os.ReadFile(filepath.Join(target, "concurrent")); readErr != nil ||
		string(content) != "keep" {
		t.Fatalf("populated directory was not restored: content=%q error=%v", content, readErr)
	}
	if _, statErr := os.Lstat(filepath.Join(parent, name)); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("private path remains after restoration: %v", statErr)
	}
}

func populatePrivateAndOccupyPublic(
	t *testing.T,
	parent string,
	name string,
	target string,
) {
	t.Helper()
	if err := os.WriteFile(
		filepath.Join(parent, name, "concurrent"),
		[]byte("keep"),
		0o600,
	); err != nil {
		t.Errorf("populate renamed directory: %v", err)
	}
	if err := os.Mkdir(target, 0o700); err != nil {
		t.Errorf("occupy public name: %v", err)
	}
}

func publishManagedDirectories(
	t *testing.T,
	workspace Workspace,
	plan executor.DirectoryPlan,
) []executor.DirectoryMutation {
	t.Helper()
	mutations := make([]executor.DirectoryMutation, 0, len(plan.Missing))
	for _, requirement := range plan.Missing {
		mutations = append(
			mutations,
			publishManagedDirectory(t, workspace, plan.Roots[0], requirement),
		)
	}
	return mutations
}

func publishManagedDirectory(
	t *testing.T,
	workspace Workspace,
	root executor.RootSnapshot,
	requirement executor.DirectoryRequirement,
) executor.DirectoryMutation {
	t.Helper()
	mutation := stageManagedDirectory(t, workspace, root, requirement)
	published, err := workspace.PublishDirectory(mutation)
	if err != nil {
		t.Fatalf("PublishDirectory() error = %v", err)
	}
	if published.Entry != mutation.Entry ||
		published.Mode != executor.ManagedDirectoryMode {
		t.Fatalf("published directory = %#v", published)
	}
	mutation.Phase = executor.StepPublished
	return mutation
}

func stageManagedDirectory(
	t *testing.T,
	workspace Workspace,
	root executor.RootSnapshot,
	requirement executor.DirectoryRequirement,
) executor.DirectoryMutation {
	t.Helper()
	name, err := workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	mutation := executor.DirectoryMutation{
		Root:        root,
		Target:      requirement.Target,
		Mode:        requirement.Mode,
		PrivateName: name,
		Phase:       executor.StepPrepared,
	}
	state, err := workspace.InspectDirectory(mutation)
	if err != nil {
		t.Fatalf("InspectDirectory() error = %v", err)
	}
	mutation.Parent = state.Parent
	mutation.Entry, err = workspace.StageDirectory(mutation)
	if err != nil {
		t.Fatalf("StageDirectory() error = %v", err)
	}
	mutation.Phase = executor.StepStaged
	return mutation
}
