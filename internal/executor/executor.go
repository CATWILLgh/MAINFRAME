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
			return Result{}, executor.abort(&journal, fmt.Errorf("save prepared mutation: %w", err))
		}
		actual, applyErr := executor.applyMutation(mutation)
		if err := confirmMutation(mutation, actual); err != nil {
			cause := errors.Join(applyErr, fmt.Errorf("confirm mutation: %w", err))
			return Result{}, executor.abort(&journal, cause)
		}
		journal.Steps[len(journal.Steps)-1].After = imageOf(actual)
		if err := executor.store.Save(journal); err != nil {
			return Result{}, errors.Join(
				applyErr,
				fmt.Errorf("save confirmed mutation: %w", err),
			)
		}
		if applyErr != nil {
			return Result{}, executor.abort(&journal, fmt.Errorf("apply mutation: %w", applyErr))
		}
		journal.Steps[len(journal.Steps)-1].State = StepApplied
		if err := executor.store.Save(journal); err != nil {
			return Result{}, executor.abort(&journal, fmt.Errorf("save applied mutation: %w", err))
		}
	}
	journal.Status = TransactionCommitted
	if err := executor.store.Save(journal); err != nil {
		return Result{}, executor.abort(&journal, fmt.Errorf("commit transaction journal: %w", err))
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
	mutation := JournalMutation{
		Location: operation.Artifact.Location,
		Before:   imageOf(before),
		Parent:   before.Parent,
		State:    StepPrepared,
	}
	switch operation.Kind {
	case domain.OperationInstall:
		if before.Exists {
			return JournalMutation{}, errors.New("install target appeared after preview")
		}
		target, err := executor.workspace.ResolveSource(operation.SourcePath)
		if err != nil {
			return JournalMutation{}, err
		}
		mutation.Kind = MutationInstall
		mutation.SourcePath = operation.SourcePath
		mutation.After = LinkImage{Exists: true, RawTarget: target}
	case domain.OperationRemove:
		target, err := executor.workspace.ResolveSource(operation.SourcePath)
		if err != nil {
			return JournalMutation{}, err
		}
		if !before.Exists || before.RawTarget != target {
			return JournalMutation{}, errors.New("remove target changed after preview")
		}
		mutation.Kind = MutationRemove
		mutation.SourcePath = operation.SourcePath
	default:
		return JournalMutation{}, fmt.Errorf("unsupported operation %q", operation.Kind)
	}
	return mutation, nil
}

func (executor Executor) applyMutation(mutation JournalMutation) (LinkState, error) {
	return executor.workspace.CompareAndSwapLink(
		mutation.Location,
		stateOf(mutation.Before, mutation.Parent),
		stateOf(mutation.After, mutation.Parent),
	)
}

func confirmMutation(mutation JournalMutation, actual LinkState) error {
	expected := stateOf(mutation.After, mutation.Parent)
	if actual.Exists != expected.Exists ||
		actual.RawTarget != expected.RawTarget ||
		actual.Parent != expected.Parent {
		return errors.New("workspace returned an unexpected after-image")
	}
	if actual.Exists && !validFileIdentity(actual.Entry) {
		return errors.New("workspace returned an after-image without identity")
	}
	if !actual.Exists && actual.Entry != (FileIdentity{}) {
		return errors.New("absent after-image has an identity")
	}
	return nil
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
