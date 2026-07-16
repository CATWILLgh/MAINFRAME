//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func (workspace Workspace) PublishConfiguration(
	mutation executor.JournalConfigurationMutation,
) (executor.ConfigurationState, error) {
	if !validFileIdentity(mutation.StagedIdentity) {
		return executor.ConfigurationState{}, errors.New("invalid staged configuration identity")
	}
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	defer context.close()
	public, staged, err := inspectConfigurationPair(context, mutation)
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	if publishedConfigurationState(public, staged, mutation) {
		return public, syncRenamedDirectories(context.privateFD, context.parentFD)
	}
	if !initialConfigurationState(public, staged, mutation) {
		return executor.ConfigurationState{}, errors.New(
			"configuration publication state changed",
		)
	}
	if mutation.Before.Exists {
		err = renameExchange(
			context.privateFD,
			mutation.StagedName,
			context.parentFD,
			context.finalName,
		)
	} else {
		err = renameNoReplace(
			context.privateFD,
			mutation.StagedName,
			context.parentFD,
			context.finalName,
		)
	}
	if err != nil {
		return inferConfigurationPublication(
			context,
			mutation,
			fmt.Errorf("publish configuration: %w", err),
		)
	}
	syncErr := syncRenamedDirectories(context.privateFD, context.parentFD)
	return inferConfigurationPublication(context, mutation, syncErr)
}

func inferConfigurationPublication(
	context configurationContext,
	mutation executor.JournalConfigurationMutation,
	operationErr error,
) (executor.ConfigurationState, error) {
	public, staged, inspectErr := inspectConfigurationPair(context, mutation)
	if inspectErr == nil && publishedConfigurationState(public, staged, mutation) {
		return public, operationErr
	}
	if operationErr != nil {
		return executor.ConfigurationState{}, errors.Join(operationErr, inspectErr)
	}
	return executor.ConfigurationState{}, errors.Join(
		inspectErr,
		errors.New("published configuration state differs"),
	)
}

func (workspace Workspace) RollbackConfiguration(
	mutation executor.JournalConfigurationMutation,
) error {
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	public, staged, err := inspectConfigurationPair(context, mutation)
	if err != nil {
		return err
	}
	if initialConfigurationState(public, staged, mutation) {
		return syncRenamedDirectories(context.parentFD, context.privateFD)
	}
	if !publishedConfigurationState(public, staged, mutation) {
		return errors.New("configuration rollback state changed")
	}
	if mutation.Before.Exists {
		err = renameExchange(
			context.privateFD,
			mutation.StagedName,
			context.parentFD,
			context.finalName,
		)
	} else {
		err = renameNoReplace(
			context.parentFD,
			context.finalName,
			context.privateFD,
			mutation.StagedName,
		)
	}
	if err != nil {
		return fmt.Errorf("rollback configuration: %w", err)
	}
	if err := syncRenamedDirectories(context.parentFD, context.privateFD); err != nil {
		return err
	}
	public, staged, err = inspectConfigurationPair(context, mutation)
	if err != nil || !initialConfigurationState(public, staged, mutation) {
		return errors.Join(err, errors.New("configuration rollback differs"))
	}
	return nil
}

func inspectConfigurationPair(
	context configurationContext,
	mutation executor.JournalConfigurationMutation,
) (executor.ConfigurationState, executor.ConfigurationState, error) {
	public, err := inspectConfigurationAt(
		context.parentFD,
		context.finalName,
		context.parent,
	)
	if err != nil {
		return executor.ConfigurationState{}, executor.ConfigurationState{}, err
	}
	staged, err := inspectPrivateConfiguration(
		context.privateFD,
		mutation.StagedName,
		context.parent,
	)
	return public, staged, err
}

func initialConfigurationState(
	public, staged executor.ConfigurationState,
	mutation executor.JournalConfigurationMutation,
) bool {
	before := mutation.Before
	after := mutation.After
	after.Entry = mutation.StagedIdentity
	return matchesConfigurationImage(public, before) &&
		matchesConfigurationImage(staged, after)
}

func publishedConfigurationState(
	public, staged executor.ConfigurationState,
	mutation executor.JournalConfigurationMutation,
) bool {
	after := mutation.After
	after.Entry = mutation.StagedIdentity
	if !matchesConfigurationImage(public, after) {
		return false
	}
	if !mutation.Before.Exists {
		return !staged.Exists
	}
	return matchesConfigurationImage(staged, mutation.Before)
}

func (workspace Workspace) FinalizeConfiguration(
	mutation executor.JournalConfigurationMutation,
) error {
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	expected, shouldExist, err := finalizedPrivateImage(mutation)
	if err != nil {
		return err
	}
	staged, err := inspectPrivateConfiguration(
		context.privateFD,
		mutation.StagedName,
		context.parent,
	)
	if err != nil {
		return err
	}
	if !staged.Exists {
		return syncDirectory(context.privateFD)
	}
	if !shouldExist || !matchesConfigurationImage(staged, expected) {
		return errors.New("private configuration differs; refusing deletion")
	}
	if err := unix.Unlinkat(context.privateFD, mutation.StagedName, 0); err != nil {
		return fmt.Errorf("remove private configuration: %w", err)
	}
	return syncDirectory(context.privateFD)
}

func finalizedPrivateImage(
	mutation executor.JournalConfigurationMutation,
) (executor.ConfigurationFileImage, bool, error) {
	switch mutation.Phase {
	case executor.StepPublished:
		return mutation.Before, mutation.Before.Exists, nil
	case executor.StepRolledBack:
		after := mutation.After
		after.Entry = mutation.StagedIdentity
		return after, true, nil
	default:
		return executor.ConfigurationFileImage{}, false, errors.New(
			"configuration is not ready for finalization",
		)
	}
}
