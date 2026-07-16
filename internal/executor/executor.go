package executor

import (
	"errors"
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Executor struct {
	locker    Locker
	store     JournalStore
	refresher Refresher
	workspace LinkWorkspace
}

func New(locker Locker, store JournalStore, refresher Refresher, workspace LinkWorkspace) Executor {
	return Executor{locker: locker, store: store, refresher: refresher, workspace: workspace}
}

func (executor Executor) Apply(preview Preview) (Result, error) {
	return executor.withLock(func() (Result, error) {
		if _, err := executor.recoverLocked(); err != nil {
			return Result{}, fmt.Errorf("recover unfinished transaction: %w", err)
		}
		fresh, err := executor.refresher.Refresh(append([]domain.ComponentID(nil), preview.Desired...))
		if err != nil {
			return Result{}, fmt.Errorf("refresh preview: %w", err)
		}
		if !reflect.DeepEqual(preview, fresh) {
			return Result{}, errors.New("preview changed; review the fresh plan before applying")
		}
		if err := validatePreview(fresh); err != nil {
			return Result{}, err
		}
		return executor.execute(fresh)
	})
}

func (executor Executor) Recover() (Result, error) {
	return executor.withLock(executor.recoverLocked)
}

func (executor Executor) withLock(operation func() (Result, error)) (result Result, err error) {
	lock, err := executor.locker.Lock()
	if err != nil {
		return Result{}, fmt.Errorf("acquire transaction lock: %w", err)
	}
	defer func() {
		unlockErr := lock.Unlock()
		if unlockErr == nil {
			return
		}
		wrapped := fmt.Errorf("release transaction lock: %w", unlockErr)
		if err != nil {
			err = errors.Join(err, wrapped)
			return
		}
		result.Warnings = append(result.Warnings, wrapped.Error())
	}()
	return operation()
}

func (executor Executor) execute(preview Preview) (Result, error) {
	journal := Journal{
		Release: preview.Release,
		Desired: append([]domain.ComponentID(nil), preview.Desired...),
		Status:  TransactionInProgress,
	}
	for _, operation := range preview.Plan.Operations {
		mutation, err := executor.prepare(operation)
		if err != nil {
			return Result{}, executor.abort(&journal, fmt.Errorf("prepare mutation: %w", err))
		}
		journal.Steps = append(journal.Steps, mutation)
		if err := executor.store.Save(journal); err != nil {
			return Result{}, executor.abortAfterSaveFailure(
				&journal,
				fmt.Errorf("save allocated mutation: %w", err),
			)
		}
		index := len(journal.Steps) - 1
		if err := executor.executeStep(&journal, index); err != nil {
			return Result{}, executor.abort(&journal, err)
		}
	}
	if len(journal.Steps) == 0 {
		return Result{}, nil
	}
	journal.Status = TransactionCommitted
	if err := executor.store.Save(journal); err != nil {
		return Result{}, fmt.Errorf(
			"commit transaction journal; recovery required: %w",
			err,
		)
	}
	if err := executor.finalizeCommitted(&journal); err != nil {
		return Result{}, fmt.Errorf("finalize committed transaction: %w", err)
	}
	if err := executor.store.Cleanup(); err != nil {
		return Result{Warnings: []string{fmt.Sprintf("cleanup committed journal: %v", err)}}, nil
	}
	return Result{}, nil
}

func (executor Executor) prepare(operation domain.Operation) (JournalMutation, error) {
	before, err := executor.workspace.Inspect(operation.Artifact.Location)
	if err != nil {
		return JournalMutation{}, err
	}
	target, err := executor.workspace.ResolveSource(operation.SourcePath)
	if err != nil {
		return JournalMutation{}, err
	}
	mutation := JournalMutation{
		Location:   operation.Artifact.Location,
		SourcePath: operation.SourcePath,
		Before:     imageOf(before),
		Parent:     before.Parent,
		Phase:      StepPrepared,
	}
	switch operation.Kind {
	case domain.OperationInstall:
		if before.Exists {
			return JournalMutation{}, errors.New("install target appeared after preview")
		}
		mutation.Kind = MutationInstall
		mutation.After = LinkImage{Exists: true, RawTarget: target}
		mutation.StagedName = "staged"
	case domain.OperationRemove:
		if !before.Exists || before.RawTarget != target {
			return JournalMutation{}, errors.New("remove target changed after preview")
		}
		mutation.Kind = MutationRemove
		mutation.RetainedName = "retained"
	default:
		return JournalMutation{}, fmt.Errorf("unsupported operation %q", operation.Kind)
	}
	privateName, err := executor.workspace.AllocatePrivateName()
	if err != nil {
		return JournalMutation{}, err
	}
	mutation.Private.Name = privateName
	return mutation, nil
}

func (executor Executor) executeStep(journal *Journal, index int) error {
	if err := executor.preparePrivate(journal, index); err != nil {
		return fmt.Errorf("prepare private workspace: %w", err)
	}
	if journal.Steps[index].Kind == MutationInstall {
		if err := executor.stageInstall(journal, index); err != nil {
			return fmt.Errorf("stage install: %w", err)
		}
	}
	step := &journal.Steps[index]
	actual, publishErr := executor.publish(*step)
	if err := confirmPublished(*step, actual); err != nil {
		return errors.Join(publishErr, fmt.Errorf("confirm publication: %w", err))
	}
	step.After = imageOf(actual)
	step.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(
			journal,
			errors.Join(publishErr, fmt.Errorf("save published mutation: %w", err)),
		)
	}
	if publishErr != nil {
		return fmt.Errorf("publish mutation: %w", publishErr)
	}
	return nil
}

func (executor Executor) preparePrivate(journal *Journal, index int) error {
	step := &journal.Steps[index]
	identity, err := executor.workspace.PreparePrivate(workspaceMutation(*step))
	if err != nil {
		return err
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a private directory without identity")
	}
	step.Private.Identity = identity
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save private directory identity: %w", err))
	}
	return nil
}

func (executor Executor) stageInstall(journal *Journal, index int) error {
	step := &journal.Steps[index]
	identity, err := executor.workspace.StageInstall(workspaceMutation(*step))
	if err != nil {
		return err
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a staged link without identity")
	}
	step.StagedIdentity = identity
	step.Phase = StepStaged
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save staged link identity: %w", err))
	}
	return nil
}

func (executor Executor) publish(step JournalMutation) (LinkState, error) {
	mutation := workspaceMutation(step)
	if step.Kind == MutationInstall {
		return executor.workspace.PublishInstall(mutation)
	}
	return executor.workspace.PublishRemove(mutation)
}

func confirmPublished(mutation JournalMutation, actual LinkState) error {
	expected := stateOf(mutation.After, mutation.Parent)
	if actual.Exists != expected.Exists ||
		actual.RawTarget != expected.RawTarget ||
		actual.Parent != expected.Parent {
		return errors.New("workspace returned an unexpected after-image")
	}
	if actual.Exists && !validFileIdentity(actual.Entry) {
		return errors.New("workspace returned an after-image without identity")
	}
	if mutation.Kind == MutationInstall && actual.Entry != mutation.StagedIdentity {
		return errors.New("published link identity differs from staged link")
	}
	if !actual.Exists && actual.Entry != (FileIdentity{}) {
		return errors.New("absent after-image has an identity")
	}
	return nil
}

func workspaceMutation(step JournalMutation) WorkspaceMutation {
	return WorkspaceMutation{
		Kind: step.Kind, Location: step.Location,
		SourceTarget: step.After.RawTarget,
		Before:       step.Before, After: step.After, Parent: step.Parent,
		Private: step.Private, StagedName: step.StagedName,
		StagedIdentity: step.StagedIdentity, RetainedName: step.RetainedName,
		Phase: step.Phase,
	}
}

func imageOf(state LinkState) LinkImage {
	return LinkImage{Exists: state.Exists, RawTarget: state.RawTarget, Entry: state.Entry}
}

func validFileIdentity(identity FileIdentity) bool {
	return identity.Device != 0 && identity.Inode != 0
}

func stateOf(image LinkImage, parent FileIdentity) LinkState {
	return LinkState{
		Exists: image.Exists, RawTarget: image.RawTarget,
		Parent: parent, Entry: image.Entry,
	}
}
