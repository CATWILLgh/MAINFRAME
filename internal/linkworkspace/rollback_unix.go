//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func (workspace Workspace) Rollback(mutation executor.WorkspaceMutation) error {
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	switch mutation.Kind {
	case executor.MutationInstall:
		return workspace.rollbackInstall(context, mutation)
	case executor.MutationReplace:
		return workspace.rollbackReplace(context, mutation)
	case executor.MutationRemove:
		return workspace.rollbackRemove(context, mutation)
	default:
		return errors.New("invalid mutation kind")
	}
}

func (workspace Workspace) rollbackReplace(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) error {
	public, retained, err := inspectReplacePair(context, mutation)
	if err != nil {
		return err
	}
	if replacePrepared(public, retained, mutation) {
		return workspace.verifyParentIdentity(mutation)
	}
	if !replacePublished(public, retained, mutation) {
		return errors.New("replace rollback state changed")
	}
	if err := renameExchange(
		context.parentFD, context.finalName,
		context.privateFD, mutation.RetainedName,
	); err != nil {
		return fmt.Errorf("rollback replace: %w", err)
	}
	if err := syncRenamedDirectories(context.parentFD, context.privateFD); err != nil {
		return err
	}
	public, retained, err = inspectReplacePair(context, mutation)
	if err != nil || !replacePrepared(public, retained, mutation) {
		return errors.Join(err, errors.New("replace rollback differs"))
	}
	return workspace.verifyParentIdentity(mutation)
}

func (workspace Workspace) rollbackInstall(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) error {
	name := mutation.StagedName
	if mutation.RetainedName != "" {
		name = mutation.RetainedName
	}
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return err
	}
	_, privateExists, privateErr := inspectPrivateLink(
		context.privateFD, name, mutation.After.RawTarget, mutation.StagedIdentity,
	)
	if privateErr != nil {
		return privateErr
	}
	if !public.Exists && privateExists {
		return workspace.verifyParentIdentity(mutation)
	}
	if !public.Exists && name != mutation.StagedName {
		_, staged, err := inspectPrivateLink(
			context.privateFD, mutation.StagedName,
			mutation.After.RawTarget, mutation.StagedIdentity,
		)
		if err == nil && staged {
			return workspace.verifyParentIdentity(mutation)
		}
	}
	if !matchesImage(public, installImage(mutation)) || privateExists {
		return errors.New("install rollback state changed")
	}
	if err := renameNoReplace(
		context.parentFD, context.finalName, context.privateFD, name,
	); err != nil {
		return fmt.Errorf("rollback install: %w", err)
	}
	return workspace.confirmInstallRollback(context, mutation, name)
}

func (workspace Workspace) confirmInstallRollback(
	context mutationContext,
	mutation executor.WorkspaceMutation,
	name string,
) error {
	syncErr := syncRenamedDirectories(context.parentFD, context.privateFD)
	public, publicErr := inspectAt(context.parentFD, context.finalName, context.parent)
	_, private, privateErr := inspectPrivateLink(
		context.privateFD, name, mutation.After.RawTarget, mutation.StagedIdentity,
	)
	verifyErr := workspace.verifyParentIdentity(mutation)
	if syncErr == nil && publicErr == nil && !public.Exists &&
		privateErr == nil && private && verifyErr == nil {
		return nil
	}
	restoreErr := renameNoReplace(
		context.privateFD, name, context.parentFD, context.finalName,
	)
	return errors.Join(
		syncErr, publicErr, privateErr, verifyErr,
		errors.New("install rollback result changed"), restoreErr,
	)
}

func (workspace Workspace) rollbackRemove(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) error {
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return err
	}
	_, retained, retainedErr := inspectPrivateLink(
		context.privateFD, mutation.RetainedName,
		mutation.Before.RawTarget, mutation.Before.Entry,
	)
	if retainedErr != nil {
		return retainedErr
	}
	if matchesImage(public, mutation.Before) && !retained {
		return workspace.verifyParentIdentity(mutation)
	}
	if public.Exists || !retained {
		return errors.New("remove rollback state changed")
	}
	if err := renameNoReplace(
		context.privateFD, mutation.RetainedName,
		context.parentFD, context.finalName,
	); err != nil {
		return fmt.Errorf("rollback remove: %w", err)
	}
	return workspace.confirmRemoveRollback(context, mutation)
}

func (workspace Workspace) confirmRemoveRollback(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) error {
	syncErr := syncRenamedDirectories(context.privateFD, context.parentFD)
	public, publicErr := inspectAt(context.parentFD, context.finalName, context.parent)
	_, retained, retainedErr := inspectPrivateLink(
		context.privateFD, mutation.RetainedName,
		mutation.Before.RawTarget, mutation.Before.Entry,
	)
	verifyErr := workspace.verifyParentIdentity(mutation)
	if syncErr == nil && publicErr == nil &&
		matchesImage(public, mutation.Before) &&
		retainedErr == nil && !retained && verifyErr == nil {
		return nil
	}
	restoreErr := renameNoReplace(
		context.parentFD, context.finalName,
		context.privateFD, mutation.RetainedName,
	)
	return errors.Join(
		syncErr, publicErr, retainedErr, verifyErr,
		errors.New("remove rollback result changed"), restoreErr,
	)
}
