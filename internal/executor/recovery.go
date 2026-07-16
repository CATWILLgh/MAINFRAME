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
		if err := executor.finalizeCommitted(journal); err != nil {
			return Result{}, fmt.Errorf("finalize committed transaction: %w", err)
		}
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
	if len(journal.Steps) == 0 {
		return cause
	}
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

func (executor Executor) abortAfterSaveFailure(journal *Journal, cause error) error {
	if err := executor.store.Save(*journal); err != nil {
		return errors.Join(cause, fmt.Errorf("persist recoverable journal: %w", err))
	}
	return executor.abort(journal, cause)
}

func (executor Executor) persistBeforeAbort(journal *Journal, cause error) error {
	if err := executor.store.Save(*journal); err != nil {
		return errors.Join(cause, fmt.Errorf("persist recoverable journal: %w", err))
	}
	return cause
}

func (executor Executor) rollback(journal *Journal) error {
	for index := len(journal.Steps) - 1; index >= 0; index-- {
		if err := executor.ensureRollbackReady(journal, index); err != nil {
			return fmt.Errorf("prepare rollback %v: %w", journal.Steps[index].Location, err)
		}
		step := &journal.Steps[index]
		if step.Phase != StepRolledBack {
			if err := executor.workspace.Rollback(workspaceMutation(*step)); err != nil {
				return fmt.Errorf("rollback %v: %w", step.Location, err)
			}
			step.Phase = StepRolledBack
			if err := executor.store.Save(*journal); err != nil {
				return fmt.Errorf("save rolled back mutation: %w", err)
			}
		}
		if err := executor.finalizeStep(journal, index); err != nil {
			return fmt.Errorf("rollback %v: %w", step.Location, err)
		}
	}
	return nil
}

func (executor Executor) ensureRollbackReady(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if !validFileIdentity(step.Private.Identity) {
		if err := executor.preparePrivate(journal, index); err != nil {
			return err
		}
	}
	if step.Kind == MutationInstall && step.Phase == StepPrepared {
		if err := executor.stageInstall(journal, index); err != nil {
			return err
		}
	}
	return nil
}

func (executor Executor) finalizeCommitted(journal *Journal) error {
	for index := range journal.Steps {
		if err := executor.finalizeStep(journal, index); err != nil {
			return err
		}
	}
	return nil
}

func (executor Executor) finalizeStep(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if !step.Finalized {
		if err := executor.workspace.Finalize(workspaceMutation(*step)); err != nil {
			return err
		}
		step.Finalized = true
		if err := executor.store.Save(*journal); err != nil {
			return fmt.Errorf("save finalized mutation: %w", err)
		}
	}
	if err := executor.workspace.FinalizePrivate(workspaceMutation(*step)); err != nil {
		return fmt.Errorf("finalize private directory: %w", err)
	}
	return nil
}
