//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func (workspace Workspace) PublishWritableFileMigration(
	step executor.JournalMutation,
) (executor.ConfigurationState, error) {
	context, err := workspace.openConfigurationMutation(migrationConfiguration(step))
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	defer context.close()
	if published, ok := inspectPublishedMigration(context, step); ok {
		return published, syncRenamedDirectories(context.privateFD, context.parentFD)
	}
	if !inspectPreparedMigration(context, step) {
		return executor.ConfigurationState{}, errors.New("materialization migration state changed")
	}
	if err := renameExchange(
		context.privateFD, step.StagedName,
		context.parentFD, context.finalName,
	); err != nil {
		return executor.ConfigurationState{}, fmt.Errorf("publish materialization migration: %w", err)
	}
	syncErr := syncRenamedDirectories(context.privateFD, context.parentFD)
	published, ok := inspectPublishedMigration(context, step)
	if !ok {
		restoreErr := restoreChangedMigrationPublication(context, step)
		return executor.ConfigurationState{}, errors.Join(
			syncErr,
			restoreErr,
			errors.New("target changed during materialization migration; restored current entry"),
		)
	}
	return published, syncErr
}

func restoreChangedMigrationPublication(
	context configurationContext,
	step executor.JournalMutation,
) error {
	public, err := inspectConfigurationAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return err
	}
	after := step.FileAfter
	after.Entry = step.StagedIdentity
	if !matchesConfigurationImage(public, after) {
		return errors.New("cannot identify published migration file for restoration")
	}
	retainedIdentity, _, err := identityAt(context.privateFD, step.StagedName)
	if err != nil {
		return fmt.Errorf("identify displaced migration target: %w", err)
	}
	if err := renameExchange(
		context.privateFD, step.StagedName,
		context.parentFD, context.finalName,
	); err != nil {
		return fmt.Errorf("restore displaced migration target: %w", err)
	}
	if err := syncRenamedDirectories(context.privateFD, context.parentFD); err != nil {
		return err
	}
	restored, _, err := identityAt(context.parentFD, context.finalName)
	if err != nil || restored != retainedIdentity {
		return errors.Join(err, errors.New("restored migration target identity differs"))
	}
	staged, err := inspectPrivateConfiguration(context.privateFD, step.StagedName, context.parent)
	if err != nil || !matchesConfigurationImage(staged, after) {
		return errors.Join(err, errors.New("restored migration stage differs"))
	}
	return nil
}

func (workspace Workspace) RollbackWritableFileMigration(step executor.JournalMutation) error {
	context, err := workspace.openConfigurationMutation(migrationConfiguration(step))
	if err != nil {
		return err
	}
	defer context.close()
	if inspectPreparedMigration(context, step) {
		return syncRenamedDirectories(context.parentFD, context.privateFD)
	}
	if _, ok := inspectPublishedMigration(context, step); !ok {
		if err := restoreChangedMigrationPublication(context, step); err != nil {
			return errors.Join(
				err,
				errors.New("materialization migration rollback state changed"),
			)
		}
		return nil
	}
	if err := renameExchange(
		context.privateFD, step.StagedName,
		context.parentFD, context.finalName,
	); err != nil {
		return fmt.Errorf("rollback materialization migration: %w", err)
	}
	if err := syncRenamedDirectories(context.parentFD, context.privateFD); err != nil {
		return err
	}
	if !inspectPreparedMigration(context, step) {
		return errors.New("materialization migration rollback differs")
	}
	return nil
}

func (workspace Workspace) FinalizeWritableFileMigration(step executor.JournalMutation) error {
	context, err := workspace.openConfigurationMutation(migrationConfiguration(step))
	if err != nil {
		return err
	}
	defer context.close()
	exists, exact, err := inspectMigrationRetained(context, step)
	if err != nil || !exact {
		return errors.Join(err, errors.New("retained materialization migration entry differs"))
	}
	if !exists {
		return syncDirectory(context.privateFD)
	}
	if err := unix.Unlinkat(context.privateFD, step.StagedName, 0); err != nil {
		return fmt.Errorf("remove retained materialization migration entry: %w", err)
	}
	return syncDirectory(context.privateFD)
}

func migrationConfiguration(step executor.JournalMutation) executor.JournalConfigurationMutation {
	return executor.JournalConfigurationMutation{
		Disposition: executor.ConfigurationPresent,
		Target:      step.Location, After: step.FileAfter, Parent: step.Parent,
		Private: step.Private, StagedName: step.StagedName,
		StagedIdentity: step.StagedIdentity, Phase: step.Phase, Finalized: step.Finalized,
	}
}

func inspectPreparedMigration(context configurationContext, step executor.JournalMutation) bool {
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil || !matchesImage(public, step.Before) {
		return false
	}
	staged, err := inspectPrivateConfiguration(context.privateFD, step.StagedName, context.parent)
	if err != nil {
		return false
	}
	after := step.FileAfter
	after.Entry = step.StagedIdentity
	return matchesConfigurationImage(staged, after)
}

func inspectPublishedMigration(
	context configurationContext,
	step executor.JournalMutation,
) (executor.ConfigurationState, bool) {
	public, err := inspectConfigurationAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return executor.ConfigurationState{}, false
	}
	after := step.FileAfter
	after.Entry = step.StagedIdentity
	if !matchesConfigurationImage(public, after) {
		return executor.ConfigurationState{}, false
	}
	retained, err := inspectAt(context.privateFD, step.StagedName, context.parent)
	return public, err == nil && matchesImage(retained, step.Before)
}

func inspectMigrationRetained(
	context configurationContext,
	step executor.JournalMutation,
) (bool, bool, error) {
	if step.Phase == executor.StepPublished {
		state, err := inspectAt(context.privateFD, step.StagedName, context.parent)
		return state.Exists, err == nil && (!state.Exists || matchesImage(state, step.Before)), err
	}
	if step.Phase == executor.StepRolledBack {
		state, err := inspectPrivateConfiguration(context.privateFD, step.StagedName, context.parent)
		after := step.FileAfter
		after.Entry = step.StagedIdentity
		return state.Exists, err == nil && (!state.Exists || matchesConfigurationImage(state, after)), err
	}
	return false, false, errors.New("materialization migration is not finalized")
}
