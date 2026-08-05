package executor

import (
	"errors"
	"fmt"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (executor Executor) recoverLocked() (Result, error) {
	journal, err := executor.store.Load()
	if err != nil {
		return Result{}, fmt.Errorf("load transaction journal: %w", err)
	}
	if journal == nil {
		return Result{}, nil
	}
	if len(journal.Configurations) > 0 && executor.configurations == nil {
		return Result{}, errors.New("configuration workspace is required for recovery")
	}
	if journalHasWritableFiles(*journal) && executor.configurations == nil {
		return Result{}, errors.New("configuration workspace is required for writable-file recovery")
	}
	if err := validateJournal(*journal); err != nil {
		return Result{}, fmt.Errorf("validate transaction journal: %w", err)
	}
	if err := executor.validateRecoveryRoots(*journal); err != nil {
		return Result{}, fmt.Errorf("validate recovery roots: %w", err)
	}
	if journal.Status == TransactionCommitted {
		if err := executor.finalizeCommitted(journal); err != nil {
			return Result{}, fmt.Errorf("finalize committed transaction: %w", err)
		}
		if err := executor.store.Cleanup(); err != nil {
			return Result{}, fmt.Errorf("cleanup committed journal: %w", err)
		}
		return Result{Recovered: true}, nil
	}
	if err := executor.checkDirectoryModes(
		preparedDirectoryRequirements(journal.Directories),
		configurationPrivateRequired(journal.Configurations),
	); err != nil {
		return Result{}, fmt.Errorf("check recovery directory mode: %w", err)
	}
	if err := executor.rollback(journal); err != nil {
		return Result{}, err
	}
	if err := executor.store.Cleanup(); err != nil {
		return Result{}, fmt.Errorf("cleanup rolled back journal: %w", err)
	}
	return Result{Recovered: true}, nil
}

func preparedDirectoryRequirements(
	directories []JournalDirectory,
) []DirectoryRequirement {
	var requirements []DirectoryRequirement
	for _, directory := range directories {
		if directory.Phase == StepPrepared &&
			validFileIdentity(directory.Parent) {
			requirements = append(requirements, DirectoryRequirement{
				Target: directory.Target,
				Mode:   directory.Mode,
			})
		}
	}
	return requirements
}

func (executor Executor) validateRecoveryRoots(journal Journal) error {
	targets := journalConfigurationTargets(journal.Configurations)
	current, err := executor.workspace.PlanDirectories(
		directoryPlanningPlan(journal.Plan, targets),
	)
	if err != nil {
		return err
	}
	if len(current.Roots) != len(journal.Roots) {
		return errors.New("configured roots differ from the transaction journal")
	}
	configured := make(map[string]bool, len(current.Roots))
	for _, root := range current.Roots {
		configured[configuredRootKey(root)] = true
	}
	for _, root := range journal.Roots {
		if !configured[configuredRootKey(root)] {
			return errors.New("configured roots differ from the transaction journal")
		}
	}
	return nil
}

func configuredRootKey(root RootSnapshot) string {
	physical := filepath.Clean(filepath.Join(
		root.AnchorPath,
		filepath.FromSlash(root.RootPath),
	))
	return string(root.Root) + "\x00" + physical
}

func (executor Executor) abort(journal *Journal, cause error) error {
	if !hasMutations(*journal) {
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
	if err := executor.rollbackConfigurations(journal); err != nil {
		return err
	}
	for index := len(journal.Steps) - 1; index >= 0; index-- {
		if err := executor.rollbackClaim(journal, index); err != nil {
			return fmt.Errorf("rollback ownership %v: %w", journal.Steps[index].Location, err)
		}
		if err := executor.ensureRollbackReady(journal, index); err != nil {
			return fmt.Errorf("prepare rollback %v: %w", journal.Steps[index].Location, err)
		}
		step := &journal.Steps[index]
		if claimOnlyMutation(step.Kind) {
			step.Phase = StepRolledBack
			step.Finalized = true
			if err := executor.store.Save(*journal); err != nil {
				return fmt.Errorf("save rolled back relinquishment: %w", err)
			}
			continue
		}
		if step.Materialization == domain.MaterializationWritableFile {
			if step.Phase != StepRolledBack {
				if err := executor.rollbackWritableFile(*step); err != nil {
					return fmt.Errorf("rollback writable file %v: %w", step.Location, err)
				}
				step.Phase = StepRolledBack
				if err := executor.store.Save(*journal); err != nil {
					return fmt.Errorf("save rolled back writable file: %w", err)
				}
			}
			if err := executor.finalizeStep(journal, index); err != nil {
				return fmt.Errorf("rollback writable file %v: %w", step.Location, err)
			}
			continue
		}
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
	for index := len(journal.Directories) - 1; index >= 0; index-- {
		if err := executor.ensureDirectoryRollbackReady(journal, index); err != nil {
			return fmt.Errorf(
				"prepare directory rollback %v: %w",
				journal.Directories[index].Target,
				err,
			)
		}
		directory := &journal.Directories[index]
		if directory.Phase != StepRolledBack {
			if err := executor.workspace.RollbackDirectory(
				directoryMutation(*journal, *directory),
			); err != nil {
				return fmt.Errorf("rollback directory %v: %w", directory.Target, err)
			}
			directory.Phase = StepRolledBack
			if err := executor.store.Save(*journal); err != nil {
				return fmt.Errorf("save rolled back directory: %w", err)
			}
		}
		if err := executor.finalizeDirectory(journal, index); err != nil {
			return fmt.Errorf("rollback directory %v: %w", directory.Target, err)
		}
	}
	return nil
}

func (executor Executor) rollbackWritableFile(step JournalMutation) error {
	if !writableFileMigration(step) {
		return executor.configurations.RollbackConfiguration(writableConfigurationMutation(step))
	}
	workspace, err := executor.writableFileMigrationWorkspace()
	if err != nil {
		return err
	}
	return workspace.RollbackWritableFileMigration(step)
}

func (executor Executor) ensureDirectoryRollbackReady(
	journal *Journal,
	index int,
) error {
	directory := &journal.Directories[index]
	if directory.Phase != StepPrepared {
		return nil
	}
	if !validFileIdentity(directory.Parent) {
		if directory.Parent == (FileIdentity{}) {
			directory.Phase = StepRolledBack
			directory.Finalized = true
			return executor.store.Save(*journal)
		}
		state, err := executor.workspace.InspectDirectory(
			directoryMutation(*journal, *directory),
		)
		if err != nil {
			return err
		}
		if state.Exists || !validFileIdentity(state.Parent) {
			return errors.New("managed directory changed before rollback")
		}
		directory.Parent = state.Parent
		if err := executor.store.Save(*journal); err != nil {
			return fmt.Errorf("save managed directory parent identity: %w", err)
		}
	}
	identity, err := executor.workspace.StageDirectory(
		directoryMutation(*journal, *directory),
	)
	if err != nil {
		return err
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a managed directory without identity")
	}
	directory.Entry = identity
	directory.Phase = StepStaged
	return executor.store.Save(*journal)
}

func (executor Executor) ensureRollbackReady(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if claimOnlyMutation(step.Kind) {
		return nil
	}
	if step.Materialization == domain.MaterializationWritableFile {
		if !validFileIdentity(step.Private.Identity) {
			if err := executor.prepareWritablePrivate(journal, index); err != nil {
				return err
			}
		}
		return executor.adoptWritableFileStage(journal, index)
	}
	if !validFileIdentity(step.Private.Identity) {
		if err := executor.preparePrivate(journal, index); err != nil {
			return err
		}
	}
	if (step.Kind == MutationInstall || step.Kind == MutationReplace) &&
		step.Phase == StepPrepared {
		if err := executor.stageInstall(journal, index); err != nil {
			return err
		}
	}
	return nil
}

func (executor Executor) finalizeCommitted(journal *Journal) error {
	if err := executor.finalizeCommittedConfigurations(journal); err != nil {
		return err
	}
	for index := range journal.Steps {
		if err := executor.finalizeStep(journal, index); err != nil {
			return err
		}
	}
	for index := range journal.Directories {
		if err := executor.finalizeDirectory(journal, index); err != nil {
			return err
		}
	}
	return nil
}

func (executor Executor) finalizeDirectory(journal *Journal, index int) error {
	directory := &journal.Directories[index]
	if directory.Finalized {
		return nil
	}
	if err := executor.workspace.FinalizeDirectory(
		directoryMutation(*journal, *directory),
	); err != nil {
		return err
	}
	directory.Finalized = true
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save finalized directory: %w", err)
	}
	return nil
}

func (executor Executor) finalizeStep(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if claimOnlyMutation(step.Kind) {
		if !step.Finalized {
			step.Finalized = true
			return executor.store.Save(*journal)
		}
		return nil
	}
	if step.Materialization == domain.MaterializationWritableFile {
		return executor.finalizeWritableFileStep(journal, index)
	}
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

func (executor Executor) rollbackClaim(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if step.ClaimPhase == "" || step.ClaimPhase == ClaimRolledBack {
		return nil
	}
	registry, err := executor.ownership.LoadOwnership()
	if err != nil {
		return err
	}
	updated, err := transitionRegistry(registry, step.ClaimAfter, step.ClaimBefore)
	if err != nil {
		return err
	}
	if err := executor.ownership.SaveOwnership(updated); err != nil {
		return err
	}
	step.ClaimPhase = ClaimRolledBack
	return executor.store.Save(*journal)
}
