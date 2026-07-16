package executor

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestApplyRejectsChangedPreviewWithoutWorkspaceWrites(t *testing.T) {
	original := testPreview("release", "digest-a", []domain.ComponentID{"codex"}, install("one", "source/one"))
	refreshed := testPreview("release", "digest-b", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(refreshed)

	result, err := fixture.executor().Apply(original)

	if err == nil || !strings.Contains(err.Error(), "preview changed") {
		t.Fatalf("expected changed preview error, got result %#v, error %v", result, err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatalf("stale preview wrote workspace or journal: writes=%d saves=%d", fixture.workspace.writeCount(), len(fixture.store.saves))
	}
}

func TestApplyRejectsChangedPlanWithSameReleaseIdentity(t *testing.T) {
	original := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	refreshed := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("two", "source/two"))
	fixture := newFixture(refreshed)

	_, err := fixture.executor().Apply(original)

	if err == nil || !strings.Contains(err.Error(), "preview changed") {
		t.Fatalf("expected stale plan error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("changed plan caused writes")
	}
}

func TestApplyRejectsPlanConflictWithoutWorkspaceWrites(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, conflict("one"))
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "conflict") {
		t.Fatalf("expected conflict error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatalf("conflict wrote workspace or journal: writes=%d saves=%d", fixture.workspace.writeCount(), len(fixture.store.saves))
	}
}

func TestApplyUsesFreshDesiredAndRequiresExactOrdering(t *testing.T) {
	original := testPreview("release", "digest", []domain.ComponentID{"codex", "claude-code"})
	refreshed := testPreview("release", "digest", []domain.ComponentID{"claude-code", "codex"})
	fixture := newFixture(refreshed)

	_, err := fixture.executor().Apply(original)

	if err == nil || !strings.Contains(err.Error(), "preview changed") {
		t.Fatalf("expected changed preview error, got %v", err)
	}
	if !reflect.DeepEqual(fixture.refresher.desired, original.Desired) {
		t.Fatalf("refresh desired = %#v, want %#v", fixture.refresher.desired, original.Desired)
	}
}

func TestApplyDeniesConcurrentTransaction(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"})
	fixture := newFixture(preview)
	fixture.locker.err = errors.New("already locked")

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "already locked") {
		t.Fatalf("expected lock denial, got %v", err)
	}
	if fixture.refresher.calls != 0 || fixture.workspace.writeCount() != 0 {
		t.Fatalf("work continued after lock denial")
	}
}

func TestApplyReportsUnlockFailureAfterCommitAsWarning(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"})
	fixture := newFixture(preview)
	fixture.locker.unlockErr = errors.New("unlock failed")

	result, err := fixture.executor().Apply(preview)

	if err != nil {
		t.Fatalf("post-commit unlock failure returned an application error: %v", err)
	}
	if len(result.Warnings) != 1 || !strings.Contains(result.Warnings[0], "unlock failed") {
		t.Fatalf("warnings = %#v", result.Warnings)
	}
}

func TestApplyPreservesOperationAndUnlockFailures(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, conflict("one"))
	fixture := newFixture(preview)
	fixture.locker.unlockErr = errors.New("unlock failed")

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "conflict") ||
		!strings.Contains(err.Error(), "unlock failed") {
		t.Fatalf("combined error = %v", err)
	}
}

func TestApplyRejectsInstallTargetThatAppearedAfterRefresh(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, install("one", "source/one"))
	fixture := newFixture(preview)
	fixture.workspace.links[testLocation("one")] = linkState("foreign/target")

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "appeared after preview") {
		t.Fatalf("expected appeared target error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("appeared install target caused writes")
	}
}

func TestApplyRejectsRemoveTargetThatChangedAfterRefresh(t *testing.T) {
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, remove("one"))
	fixture := newFixture(preview)
	fixture.workspace.links[testLocation("one")] = linkState("foreign/target")

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "changed after preview") {
		t.Fatalf("expected changed remove target error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("changed remove target caused writes")
	}
}

func TestApplyRejectsOverlappingPlanLocations(t *testing.T) {
	preview := testPreview(
		"release", "digest", []domain.ComponentID{"codex"},
		install("tree", "source/tree"),
		install("tree/child", "source/child"),
	)
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "overlapping locations") {
		t.Fatalf("expected overlapping plan error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("overlapping plan caused writes")
	}
}

func TestApplyRejectsInvalidOperationComponentID(t *testing.T) {
	operation := install("one", "source/one")
	operation.ComponentID = "Invalid"
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "invalid operation") {
		t.Fatalf("expected invalid component error, got %v", err)
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("invalid operation caused writes")
	}
}

type fixture struct {
	locker    *fakeLocker
	store     *fakeStore
	refresher *fakeRefresher
	workspace *fakeWorkspace
}

func newFixture(preview Preview) *fixture {
	store := &fakeStore{}
	workspace := &fakeWorkspace{
		links:              make(map[domain.Location]LinkState),
		private:            make(map[string]*fakePrivateDirectory),
		directories:        make(map[DirectoryTarget]DirectoryState),
		privateDirectories: make(map[string]FileIdentity),
		store:              store,
	}
	return &fixture{
		locker:    &fakeLocker{},
		store:     store,
		refresher: &fakeRefresher{preview: preview},
		workspace: workspace,
	}
}

func (fixture *fixture) executor() Executor {
	return New(fixture.locker, fixture.store, fixture.refresher, fixture.workspace)
}

func testPreview(id, digest string, desired []domain.ComponentID, operations ...domain.Operation) Preview {
	return Preview{
		Release: ReleaseIdentity{ID: id, IndexSHA256: testDigest(digest)},
		Desired: append([]domain.ComponentID(nil), desired...),
		Plan:    domain.Plan{Operations: append([]domain.Operation(nil), operations...)},
	}
}

func testDigest(value string) string {
	return fmt.Sprintf("%x", sha256.Sum256([]byte(value)))
}

func testLocation(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootCodexConfig, Path: path}
}

func install(path, source domain.ArtifactPath) domain.Operation {
	return domain.Operation{
		ComponentID: "codex",
		Kind:        domain.OperationInstall,
		Artifact:    domain.Artifact{Location: testLocation(path)},
		SourcePath:  source,
	}
}

func conflict(path domain.ArtifactPath) domain.Operation {
	return domain.Operation{
		ComponentID: "codex",
		Kind:        domain.OperationConflict,
		Artifact:    domain.Artifact{Location: testLocation(path), Ownership: domain.OwnershipConflict},
	}
}

type fakeLock struct {
	unlocked bool
	err      error
}

func (lock *fakeLock) Unlock() error {
	lock.unlocked = true
	return lock.err
}

type fakeLocker struct {
	err       error
	unlockErr error
	lock      *fakeLock
}

func (locker *fakeLocker) Lock() (Lock, error) {
	if locker.err != nil {
		return nil, locker.err
	}
	locker.lock = &fakeLock{err: locker.unlockErr}
	return locker.lock, nil
}

type fakeStore struct {
	journal              *Journal
	saves                []Journal
	loadErr              error
	saveFailAt           int
	saveFailAfterWriteAt int
	saveCalls            int
	cleanupErr           error
	cleanupCalls         int
}

func (store *fakeStore) Load() (*Journal, error) {
	if store.loadErr != nil {
		return nil, store.loadErr
	}
	return cloneJournalPointer(store.journal), nil
}

func (store *fakeStore) Save(journal Journal) error {
	store.saveCalls++
	if store.saveFailAt == store.saveCalls {
		return errors.New("save failed")
	}
	store.journal = cloneJournalPointer(&journal)
	store.saves = append(store.saves, *cloneJournalPointer(&journal))
	if store.saveFailAfterWriteAt == store.saveCalls {
		return errors.New("save outcome unknown")
	}
	return nil
}

func (store *fakeStore) Cleanup() error {
	store.cleanupCalls++
	if store.cleanupErr != nil {
		return store.cleanupErr
	}
	store.journal = nil
	return nil
}

type fakeRefresher struct {
	preview Preview
	desired []domain.ComponentID
	calls   int
	err     error
}

func (refresher *fakeRefresher) Refresh(desired []domain.ComponentID) (Preview, error) {
	refresher.calls++
	refresher.desired = append([]domain.ComponentID(nil), desired...)
	if refresher.err != nil {
		return Preview{}, refresher.err
	}
	return refresher.preview, nil
}
