package executor

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type fakeWorkspace struct {
	links                map[domain.Location]LinkState
	private              map[string]*fakePrivateDirectory
	directoryPlan        *DirectoryPlan
	directoryModeErr     error
	directoryModeChecks  int
	directories          map[DirectoryTarget]DirectoryState
	privateDirectories   map[string]FileIdentity
	directoryCalls       []string
	store                *fakeStore
	writes               []string
	inspectErr           error
	inspectCalls         int
	resolveErr           error
	allocateErr          error
	prepareFailAt        int
	prepareCalls         int
	stageFailAt          int
	stageCalls           int
	publishFailAt        int
	publishCalls         int
	finalizeFailAt       int
	finalizeCalls        int
	finalizePrivateCalls int
	failAfterWrite       bool
	nextInode            uint64
	nextName             uint64
	publishSaveCount     int
	directoryInspectSave int
	directoryStageSave   int
	directoryPublishSave int
	linkInspectDirCalls  int
	linkRollbackDirCalls int
	plannedOperations    []domain.Operation
	absentPublicObserved bool
}

type fakePrivateDirectory struct {
	identity FileIdentity
	staged   *LinkState
	retained *LinkState
}

func (workspace *fakeWorkspace) Inspect(location domain.Location) (LinkState, error) {
	workspace.inspectCalls++
	workspace.linkInspectDirCalls = len(workspace.directoryCalls)
	if workspace.inspectErr != nil {
		return LinkState{}, workspace.inspectErr
	}
	state, exists := workspace.links[location]
	if !exists {
		state.Parent = testIdentity(1, 1)
	}
	return state, nil
}

func (workspace *fakeWorkspace) ResolveSource(source domain.ArtifactPath) (string, error) {
	if workspace.resolveErr != nil {
		return "", workspace.resolveErr
	}
	return string(source), nil
}

func (workspace *fakeWorkspace) AllocatePrivateName() (string, error) {
	if workspace.allocateErr != nil {
		return "", workspace.allocateErr
	}
	workspace.nextName++
	return fmt.Sprintf(".mainframe-%032x", workspace.nextName), nil
}

func (workspace *fakeWorkspace) PreparePrivate(
	mutation WorkspaceMutation,
) (FileIdentity, error) {
	workspace.prepareCalls++
	if workspace.prepareFailAt == workspace.prepareCalls {
		return FileIdentity{}, errors.New("prepare failed")
	}
	location := mutation.Location
	private := mutation.Private
	key := privateKey(location, private.Name)
	entry := workspace.private[key]
	if entry == nil {
		workspace.nextInode++
		entry = &fakePrivateDirectory{
			identity: testIdentity(1, 10+workspace.nextInode),
		}
		workspace.private[key] = entry
	}
	if private.Identity != (FileIdentity{}) && private.Identity != entry.identity {
		return FileIdentity{}, errors.New("private identity mismatch")
	}
	return entry.identity, nil
}

func (workspace *fakeWorkspace) StageInstall(mutation WorkspaceMutation) (FileIdentity, error) {
	workspace.stageCalls++
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return FileIdentity{}, err
	}
	if entry.staged == nil {
		workspace.nextInode++
		state := stateOf(
			LinkImage{
				Exists: true, RawTarget: mutation.SourceTarget,
				Entry: testIdentity(1, 100+workspace.nextInode),
			},
			mutation.Parent,
		)
		entry.staged = &state
	}
	if workspace.stageFailAt == workspace.stageCalls {
		return FileIdentity{}, errors.New("stage failed")
	}
	return entry.staged.Entry, nil
}

func (workspace *fakeWorkspace) PublishInstall(mutation WorkspaceMutation) (LinkState, error) {
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return LinkState{}, err
	}
	workspace.publishCalls++
	workspace.publishSaveCount = workspace.store.saveCalls
	fail := workspace.publishFailAt == workspace.publishCalls
	if fail && !workspace.failAfterWrite {
		return stateOf(mutation.Before, mutation.Parent), errors.New("publish failed")
	}
	current, _ := workspace.Inspect(mutation.Location)
	if current.Exists && current.Entry == mutation.StagedIdentity {
		return current, nil
	}
	if current != stateOf(mutation.Before, mutation.Parent) ||
		entry.staged == nil || entry.staged.Entry != mutation.StagedIdentity {
		return current, errors.New("publish install mismatch")
	}
	actual := *entry.staged
	entry.staged = nil
	workspace.links[mutation.Location] = actual
	workspace.recordWrite(mutation.Location, actual.RawTarget)
	if fail {
		return actual, errors.New("publish outcome unknown")
	}
	return actual, nil
}

func (workspace *fakeWorkspace) PublishReplace(mutation WorkspaceMutation) (LinkState, error) {
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return LinkState{}, err
	}
	workspace.publishCalls++
	current, _ := workspace.Inspect(mutation.Location)
	if current.Exists && current.Entry == mutation.StagedIdentity && entry.retained != nil {
		return current, nil
	}
	if current != stateOf(mutation.Before, mutation.Parent) || entry.staged == nil ||
		entry.staged.Entry != mutation.StagedIdentity || entry.retained != nil {
		return current, errors.New("publish replace mismatch")
	}
	newState := *entry.staged
	entry.staged = nil
	entry.retained = &current
	workspace.links[mutation.Location] = newState
	workspace.recordWrite(mutation.Location, newState.RawTarget)
	return newState, nil
}

func (workspace *fakeWorkspace) PublishRemove(mutation WorkspaceMutation) (LinkState, error) {
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return LinkState{}, err
	}
	workspace.publishCalls++
	workspace.publishSaveCount = workspace.store.saveCalls
	fail := workspace.publishFailAt == workspace.publishCalls
	if fail && !workspace.failAfterWrite {
		return stateOf(mutation.Before, mutation.Parent), errors.New("publish failed")
	}
	current, _ := workspace.Inspect(mutation.Location)
	if !current.Exists && entry.retained != nil && entry.retained.Entry == mutation.Before.Entry {
		return current, nil
	}
	if current != stateOf(mutation.Before, mutation.Parent) || entry.retained != nil {
		return current, errors.New("publish remove mismatch")
	}
	entry.retained = &current
	delete(workspace.links, mutation.Location)
	actual := stateOf(LinkImage{}, mutation.Parent)
	workspace.recordWrite(mutation.Location, "")
	if fail {
		return actual, errors.New("publish outcome unknown")
	}
	return actual, nil
}

func (workspace *fakeWorkspace) Rollback(mutation WorkspaceMutation) error {
	workspace.linkRollbackDirCalls = len(workspace.directoryCalls)
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return err
	}
	if mutation.Kind == MutationInstall {
		return workspace.rollbackInstall(mutation, entry)
	}
	if mutation.Kind == MutationReplace {
		return workspace.rollbackReplace(mutation, entry)
	}
	return workspace.rollbackRemove(mutation, entry)
}

func (workspace *fakeWorkspace) rollbackReplace(
	mutation WorkspaceMutation,
	private *fakePrivateDirectory,
) error {
	current, _ := workspace.Inspect(mutation.Location)
	if current == stateOf(mutation.Before, mutation.Parent) && private.staged != nil {
		return nil
	}
	if private.retained == nil || current.Entry != mutation.StagedIdentity {
		return errors.New("replace rollback identity mismatch")
	}
	old := *private.retained
	private.retained = nil
	private.staged = &current
	workspace.links[mutation.Location] = old
	workspace.recordWrite(mutation.Location, old.RawTarget)
	return nil
}

func (workspace *fakeWorkspace) rollbackInstall(
	mutation WorkspaceMutation,
	private *fakePrivateDirectory,
) error {
	current, _ := workspace.Inspect(mutation.Location)
	if current.Exists {
		expected := stateOf(
			LinkImage{
				Exists: true, RawTarget: mutation.SourceTarget,
				Entry: mutation.StagedIdentity,
			},
			mutation.Parent,
		)
		if current != expected || private.staged != nil {
			return errors.New("installed link identity mismatch")
		}
		private.staged = &current
		delete(workspace.links, mutation.Location)
		workspace.recordWrite(mutation.Location, "")
	}
	return nil
}

func (workspace *fakeWorkspace) rollbackRemove(
	mutation WorkspaceMutation,
	private *fakePrivateDirectory,
) error {
	current, _ := workspace.Inspect(mutation.Location)
	if current == stateOf(mutation.Before, mutation.Parent) && private.retained == nil {
		return nil
	}
	if current.Exists || private.retained == nil ||
		private.retained.Entry != mutation.Before.Entry {
		return errors.New("retained link identity mismatch")
	}
	workspace.links[mutation.Location] = *private.retained
	private.retained = nil
	workspace.recordWrite(mutation.Location, mutation.Before.RawTarget)
	return nil
}

func (workspace *fakeWorkspace) Finalize(mutation WorkspaceMutation) error {
	workspace.finalizeCalls++
	if workspace.finalizeFailAt == workspace.finalizeCalls {
		return errors.New("finalize failed")
	}
	entry, err := workspace.privateEntry(mutation)
	if err != nil {
		return err
	}
	if mutation.Kind == MutationInstall {
		entry.staged = nil
	} else if mutation.Kind == MutationReplace {
		entry.retained = nil
	} else {
		entry.retained = nil
	}
	return nil
}

func (workspace *fakeWorkspace) FinalizePrivate(mutation WorkspaceMutation) error {
	workspace.finalizePrivateCalls++
	key := privateKey(mutation.Location, mutation.Private.Name)
	entry := workspace.private[key]
	if entry == nil {
		return nil
	}
	if entry.identity != mutation.Private.Identity ||
		entry.staged != nil || entry.retained != nil {
		return errors.New("private directory not empty or identity changed")
	}
	delete(workspace.private, key)
	return nil
}

func (workspace *fakeWorkspace) privateEntry(
	mutation WorkspaceMutation,
) (*fakePrivateDirectory, error) {
	key := privateKey(mutation.Location, mutation.Private.Name)
	entry := workspace.private[key]
	if entry == nil {
		entry = recoverFakePrivate(mutation)
		workspace.private[key] = entry
	}
	if entry.identity != mutation.Private.Identity {
		return nil, errors.New("private directory identity mismatch")
	}
	return entry, nil
}

func recoverFakePrivate(mutation WorkspaceMutation) *fakePrivateDirectory {
	entry := &fakePrivateDirectory{identity: mutation.Private.Identity}
	if mutation.Kind == MutationInstall && mutation.Phase == StepStaged {
		state := stateOf(
			LinkImage{
				Exists: true, RawTarget: mutation.SourceTarget,
				Entry: mutation.StagedIdentity,
			},
			mutation.Parent,
		)
		entry.staged = &state
	}
	if mutation.Kind == MutationReplace {
		if mutation.Phase == StepStaged || mutation.Phase == StepRolledBack {
			state := stateOf(LinkImage{
				Exists: true, RawTarget: mutation.SourceTarget, Entry: mutation.StagedIdentity,
			}, mutation.Parent)
			entry.staged = &state
		}
		if mutation.Phase == StepPublished {
			state := stateOf(mutation.Before, mutation.Parent)
			entry.retained = &state
		}
	}
	if mutation.Kind == MutationRemove && mutation.Phase == StepPublished {
		state := stateOf(mutation.Before, mutation.Parent)
		entry.retained = &state
	}
	return entry
}

func (workspace *fakeWorkspace) recordWrite(location domain.Location, target string) {
	workspace.writes = append(workspace.writes, string(location.Path)+":"+target)
}

func privateKey(location domain.Location, name string) string {
	return string(location.Root) + "/" + string(location.Path) + "/" + name
}

func (workspace *fakeWorkspace) writeCount() int {
	return len(workspace.writes)
}

func (workspace *fakeWorkspace) filesystemCalls() int {
	return workspace.inspectCalls + workspace.prepareCalls + workspace.stageCalls +
		workspace.publishCalls + workspace.finalizeCalls + workspace.finalizePrivateCalls +
		len(workspace.directoryCalls)
}
