//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

type directoryContext struct {
	parentFD int
	final    string
	parent   executor.FileIdentity
}

func (context directoryContext) close() {
	unix.Close(context.parentFD)
}

func (workspace Workspace) InspectDirectory(
	mutation executor.DirectoryMutation,
) (executor.DirectoryState, error) {
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		return executor.DirectoryState{}, err
	}
	defer context.close()
	return inspectDirectoryAt(context.parentFD, context.final, context.parent)
}

func (workspace Workspace) StageDirectory(
	mutation executor.DirectoryMutation,
) (executor.FileIdentity, error) {
	if !validFileIdentity(mutation.Parent) {
		return executor.FileIdentity{}, errors.New("invalid managed directory parent")
	}
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		return executor.FileIdentity{}, err
	}
	defer context.close()
	identity, exists, err := inspectPrivateDirectory(
		context.parentFD,
		mutation.PrivateName,
		mutation.Entry,
		mutation.Mode,
	)
	if err != nil || exists {
		return identity, err
	}
	if err := unix.Mkdirat(
		context.parentFD,
		mutation.PrivateName,
		mutation.Mode,
	); err != nil {
		if !errors.Is(err, unix.EEXIST) {
			return executor.FileIdentity{}, fmt.Errorf("stage managed directory: %w", err)
		}
		identity, _, adoptErr := inspectPrivateDirectory(
			context.parentFD,
			mutation.PrivateName,
			mutation.Entry,
			mutation.Mode,
		)
		return identity, adoptErr
	}
	if err := syncDirectory(context.parentFD); err != nil {
		return executor.FileIdentity{}, err
	}
	identity, exists, err = inspectPrivateDirectory(
		context.parentFD,
		mutation.PrivateName,
		executor.FileIdentity{},
		mutation.Mode,
	)
	if err != nil || !exists {
		return executor.FileIdentity{}, errors.Join(
			err,
			errors.New("staged managed directory disappeared"),
		)
	}
	return identity, verifyDirectoryParent(context, mutation)
}

func (workspace Workspace) PublishDirectory(
	mutation executor.DirectoryMutation,
) (executor.DirectoryState, error) {
	if !validFileIdentity(mutation.Parent) || !validFileIdentity(mutation.Entry) {
		return executor.DirectoryState{}, errors.New("invalid managed directory identity")
	}
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		return executor.DirectoryState{}, err
	}
	defer context.close()
	public, err := inspectDirectoryAt(context.parentFD, context.final, context.parent)
	if err != nil {
		return executor.DirectoryState{}, err
	}
	_, privateExists, privateErr := inspectPrivateDirectory(
		context.parentFD,
		mutation.PrivateName,
		mutation.Entry,
		mutation.Mode,
	)
	if privateErr != nil {
		return executor.DirectoryState{}, privateErr
	}
	if matchesDirectory(public, mutation) && !privateExists {
		return public, verifyDirectoryParent(context, mutation)
	}
	if public.Exists || !privateExists {
		return executor.DirectoryState{}, errors.New("managed directory publication state changed")
	}
	if err := renameNoReplace(
		context.parentFD,
		mutation.PrivateName,
		context.parentFD,
		context.final,
	); err != nil {
		return executor.DirectoryState{}, fmt.Errorf("publish managed directory: %w", err)
	}
	return confirmDirectoryPublication(context, mutation)
}

func confirmDirectoryPublication(
	context directoryContext,
	mutation executor.DirectoryMutation,
) (executor.DirectoryState, error) {
	syncErr := syncDirectory(context.parentFD)
	actual, inspectErr := inspectDirectoryAt(
		context.parentFD,
		context.final,
		context.parent,
	)
	verifyErr := verifyDirectoryParent(context, mutation)
	if syncErr == nil && inspectErr == nil && verifyErr == nil &&
		matchesDirectory(actual, mutation) {
		return actual, nil
	}
	restoreErr := renameNoReplace(
		context.parentFD,
		context.final,
		context.parentFD,
		mutation.PrivateName,
	)
	restoreSyncErr := error(nil)
	if restoreErr == nil {
		restoreSyncErr = syncDirectory(context.parentFD)
	}
	return actual, errors.Join(
		syncErr,
		inspectErr,
		verifyErr,
		errors.New("published managed directory differs from staged directory"),
		restoreErr,
		restoreSyncErr,
	)
}

func (workspace Workspace) RollbackDirectory(
	mutation executor.DirectoryMutation,
) error {
	if !validFileIdentity(mutation.Parent) || !validFileIdentity(mutation.Entry) {
		return errors.New("invalid managed directory rollback identity")
	}
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	public, err := inspectDirectoryAt(context.parentFD, context.final, context.parent)
	if err != nil {
		return err
	}
	_, privateExists, privateEmpty, privateErr := inspectOwnedDirectory(
		context.parentFD,
		mutation.PrivateName,
		mutation.Entry,
		mutation.Mode,
	)
	if privateErr != nil {
		return privateErr
	}
	if !public.Exists && privateExists {
		if !privateEmpty {
			restoreErr := renameNoReplace(
				context.parentFD,
				mutation.PrivateName,
				context.parentFD,
				context.final,
			)
			restoreSyncErr := error(nil)
			if restoreErr == nil {
				restoreSyncErr = syncDirectory(context.parentFD)
			}
			return errors.Join(
				errors.New("managed directory was populated during rollback"),
				restoreErr,
				restoreSyncErr,
			)
		}
		return verifyDirectoryParent(context, mutation)
	}
	if !matchesDirectory(public, mutation) || privateExists {
		return errors.New("managed directory rollback state changed")
	}
	empty, err := exactDirectoryEmpty(
		context.parentFD,
		context.final,
		mutation.Entry,
		mutation.Mode,
	)
	if err != nil || !empty {
		return errors.Join(err, errors.New("managed directory is not empty"))
	}
	return rollbackPublishedDirectory(context, mutation, nil)
}

func rollbackPublishedDirectory(
	context directoryContext,
	mutation executor.DirectoryMutation,
	afterRename func(),
) error {
	if err := renameNoReplace(
		context.parentFD,
		context.final,
		context.parentFD,
		mutation.PrivateName,
	); err != nil {
		return fmt.Errorf("rollback managed directory: %w", err)
	}
	if afterRename != nil {
		afterRename()
	}
	return confirmDirectoryRollback(context, mutation)
}

func confirmDirectoryRollback(
	context directoryContext,
	mutation executor.DirectoryMutation,
) error {
	syncErr := syncDirectory(context.parentFD)
	empty, inspectErr := exactDirectoryEmpty(
		context.parentFD,
		mutation.PrivateName,
		mutation.Entry,
		mutation.Mode,
	)
	verifyErr := verifyDirectoryParent(context, mutation)
	if syncErr == nil && inspectErr == nil && empty && verifyErr == nil {
		return nil
	}
	restoreErr := renameNoReplace(
		context.parentFD,
		mutation.PrivateName,
		context.parentFD,
		context.final,
	)
	restoreSyncErr := error(nil)
	if restoreErr == nil {
		restoreSyncErr = syncDirectory(context.parentFD)
	}
	return errors.Join(
		syncErr,
		inspectErr,
		verifyErr,
		errors.New("rolled back managed directory changed"),
		restoreErr,
		restoreSyncErr,
	)
}

func (workspace Workspace) FinalizeDirectory(
	mutation executor.DirectoryMutation,
) error {
	if mutation.Phase == executor.StepPublished {
		return nil
	}
	if mutation.Phase != executor.StepRolledBack {
		return errors.New("invalid managed directory finalization phase")
	}
	context, err := workspace.openDirectoryContext(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	_, exists, err := inspectPrivateDirectory(
		context.parentFD,
		mutation.PrivateName,
		mutation.Entry,
		mutation.Mode,
	)
	if err != nil || !exists {
		return err
	}
	if err := unix.Unlinkat(
		context.parentFD,
		mutation.PrivateName,
		unix.AT_REMOVEDIR,
	); err != nil {
		return fmt.Errorf("remove rolled back managed directory: %w", err)
	}
	return errors.Join(
		syncDirectory(context.parentFD),
		verifyDirectoryParent(context, mutation),
	)
}
