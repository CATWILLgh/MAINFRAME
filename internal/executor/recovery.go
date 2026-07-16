package executor

import (
	"errors"
	"fmt"
)

func (executor Executor) recoverLocked() (Result, error) {
	journal, err := executor.store.Load()
	if err != nil {
		return Result{}, fmt.Errorf("load transaction journal: %w", err)
	}
	if journal == nil {
		return Result{}, nil
	}
	if err := validateJournal(*journal); err != nil {
		return Result{}, fmt.Errorf("validate transaction journal: %w", err)
	}
	if journal.Status == TransactionCommitted {
		if err := executor.store.Cleanup(); err != nil {
			return Result{}, fmt.Errorf("cleanup committed journal: %w", err)
		}
		return Result{}, nil
	}
	if err := executor.rollback(journal); err != nil {
		return Result{}, err
	}
	if err := executor.store.Cleanup(); err != nil {
		return Result{}, fmt.Errorf("cleanup rolled back journal: %w", err)
	}
	return Result{}, nil
}

func (executor Executor) abort(journal *Journal, cause error) error {
	journal.Status = TransactionInProgress
	rollbackErr := executor.rollback(journal)
	if rollbackErr != nil {
		return errors.Join(cause, fmt.Errorf("rollback transaction: %w", rollbackErr))
	}
	if cleanupErr := executor.store.Cleanup(); cleanupErr != nil {
		return errors.Join(cause, fmt.Errorf("cleanup rolled back journal: %w", cleanupErr))
	}
	return cause
}

func (executor Executor) rollback(journal *Journal) error {
	for index := len(journal.Steps) - 1; index >= 0; index-- {
		step := &journal.Steps[index]
		if step.State == StepRolledBack {
			continue
		}
		if err := executor.rollbackStep(*step); err != nil {
			return fmt.Errorf("rollback %v: %w", step.Location, err)
		}
		step.State = StepRolledBack
		if err := executor.store.Save(*journal); err != nil {
			return fmt.Errorf("save rolled back mutation: %w", err)
		}
	}
	return nil
}

func (executor Executor) rollbackStep(step JournalMutation) error {
	current, err := executor.workspace.Inspect(step.Location)
	if err != nil {
		return err
	}
	if current.Parent != step.Parent {
		return errors.New("parent identity changed")
	}
	currentImage := imageOf(current)
	if currentImage == step.Before {
		return nil
	}
	if currentImage != step.After {
		return errors.New("after-image mismatch")
	}
	_, err = executor.workspace.CompareAndSwapLink(
		step.Location,
		stateOf(step.After, step.Parent),
		stateOf(step.Before, step.Parent),
	)
	return err
}
