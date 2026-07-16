//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

type mutationContext struct {
	parentFD  int
	privateFD int
	finalName string
	parent    executor.FileIdentity
}

func (context mutationContext) close() {
	unix.Close(context.privateFD)
	unix.Close(context.parentFD)
}

func (workspace Workspace) StageInstall(
	mutation executor.WorkspaceMutation,
) (executor.FileIdentity, error) {
	if mutation.Kind != executor.MutationInstall ||
		mutation.SourceTarget == "" || !validEntryName(mutation.StagedName) {
		return executor.FileIdentity{}, errors.New("invalid staged link")
	}
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return executor.FileIdentity{}, err
	}
	defer context.close()
	identity, exists, err := inspectPrivateLink(
		context.privateFD, mutation.StagedName,
		mutation.SourceTarget, mutation.StagedIdentity,
	)
	if err != nil || exists {
		return identity, err
	}
	if err := unix.Symlinkat(mutation.SourceTarget, context.privateFD, mutation.StagedName); err != nil {
		return executor.FileIdentity{}, fmt.Errorf("stage link: %w", err)
	}
	if err := syncDirectory(context.privateFD); err != nil {
		return executor.FileIdentity{}, err
	}
	identity, exists, err = inspectPrivateLink(
		context.privateFD, mutation.StagedName, mutation.SourceTarget,
		executor.FileIdentity{},
	)
	if err != nil || !exists {
		return executor.FileIdentity{}, errors.Join(err, errors.New("staged link disappeared"))
	}
	return identity, workspace.verifyParentIdentity(mutation)
}

func (workspace Workspace) PublishInstall(
	mutation executor.WorkspaceMutation,
) (executor.LinkState, error) {
	if mutation.Kind != executor.MutationInstall ||
		!validFileIdentity(mutation.StagedIdentity) {
		return executor.LinkState{}, errors.New("invalid install publication")
	}
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return executor.LinkState{}, err
	}
	defer context.close()
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return executor.LinkState{}, err
	}
	_, staged, stagedErr := inspectPrivateLink(
		context.privateFD, mutation.StagedName,
		mutation.SourceTarget, mutation.StagedIdentity,
	)
	if stagedErr != nil {
		return executor.LinkState{}, stagedErr
	}
	expected := installImage(mutation)
	if matchesImage(public, expected) && !staged {
		return public, workspace.verifyParentIdentity(mutation)
	}
	if !matchesImage(public, mutation.Before) || !staged {
		return executor.LinkState{}, errors.New("install publication state changed")
	}
	if err := renameNoReplace(
		context.privateFD, mutation.StagedName,
		context.parentFD, context.finalName,
	); err != nil {
		return executor.LinkState{}, fmt.Errorf("publish install: %w", err)
	}
	return workspace.confirmInstallPublication(context, mutation)
}

func (workspace Workspace) confirmInstallPublication(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) (executor.LinkState, error) {
	syncErr := syncRenamedDirectories(context.privateFD, context.parentFD)
	actual, inspectErr := inspectAt(context.parentFD, context.finalName, context.parent)
	verifyErr := workspace.verifyParentIdentity(mutation)
	if syncErr == nil && inspectErr == nil && verifyErr == nil &&
		matchesImage(actual, installImage(mutation)) {
		return actual, nil
	}
	restoreErr := renameNoReplace(
		context.parentFD, context.finalName,
		context.privateFD, mutation.StagedName,
	)
	restoreSyncErr := error(nil)
	if restoreErr == nil {
		restoreSyncErr = syncRenamedDirectories(context.parentFD, context.privateFD)
	}
	return actual, errors.Join(
		syncErr, inspectErr, verifyErr,
		errors.New("published install differs from staged link"),
		restoreErr, restoreSyncErr,
	)
}

func (workspace Workspace) PublishRemove(
	mutation executor.WorkspaceMutation,
) (executor.LinkState, error) {
	if mutation.Kind != executor.MutationRemove ||
		!validFileIdentity(mutation.Before.Entry) {
		return executor.LinkState{}, errors.New("invalid remove publication")
	}
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return executor.LinkState{}, err
	}
	defer context.close()
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return executor.LinkState{}, err
	}
	_, retained, retainedErr := inspectPrivateLink(
		context.privateFD, mutation.RetainedName,
		mutation.Before.RawTarget, mutation.Before.Entry,
	)
	if retainedErr != nil {
		return executor.LinkState{}, retainedErr
	}
	if !public.Exists && retained {
		return public, workspace.verifyParentIdentity(mutation)
	}
	if !matchesImage(public, mutation.Before) || retained {
		return executor.LinkState{}, errors.New("remove publication state changed")
	}
	if err := renameNoReplace(
		context.parentFD, context.finalName,
		context.privateFD, mutation.RetainedName,
	); err != nil {
		return executor.LinkState{}, fmt.Errorf("publish remove: %w", err)
	}
	return workspace.confirmRemovePublication(context, mutation)
}

func (workspace Workspace) confirmRemovePublication(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) (executor.LinkState, error) {
	syncErr := syncRenamedDirectories(context.parentFD, context.privateFD)
	actual, inspectErr := inspectAt(context.parentFD, context.finalName, context.parent)
	verifyErr := workspace.verifyParentIdentity(mutation)
	_, retained, retainedErr := inspectPrivateLink(
		context.privateFD, mutation.RetainedName,
		mutation.Before.RawTarget, mutation.Before.Entry,
	)
	if syncErr == nil && inspectErr == nil && verifyErr == nil &&
		!actual.Exists && retainedErr == nil && retained {
		return actual, nil
	}
	restoreErr := renameNoReplace(
		context.privateFD, mutation.RetainedName,
		context.parentFD, context.finalName,
	)
	restoreSyncErr := error(nil)
	if restoreErr == nil {
		restoreSyncErr = syncRenamedDirectories(context.privateFD, context.parentFD)
	}
	return actual, errors.Join(
		syncErr, inspectErr, verifyErr, retainedErr,
		errors.New("removed link was not retained exactly"),
		restoreErr, restoreSyncErr,
	)
}

func (workspace Workspace) Finalize(mutation executor.WorkspaceMutation) error {
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	switch mutation.Kind {
	case executor.MutationInstall:
		return finalizeInstall(context, mutation)
	case executor.MutationRemove:
		return removeVerifiedPrivateLink(
			context.privateFD, mutation.RetainedName,
			mutation.Before.RawTarget, mutation.Before.Entry,
		)
	default:
		return errors.New("invalid mutation kind")
	}
}

func finalizeInstall(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) error {
	if err := removeVerifiedPrivateLink(
		context.privateFD, mutation.StagedName,
		mutation.After.RawTarget, mutation.StagedIdentity,
	); err != nil {
		return err
	}
	if mutation.RetainedName == "" {
		return nil
	}
	return removeVerifiedPrivateLink(
		context.privateFD, mutation.RetainedName,
		mutation.After.RawTarget, mutation.StagedIdentity,
	)
}

func (workspace Workspace) FinalizePrivate(mutation executor.WorkspaceMutation) error {
	if !validFileIdentity(mutation.Parent) ||
		!validFileIdentity(mutation.Private.Identity) {
		return errors.New("invalid workspace identity")
	}
	parentFD, _, parent, err := workspace.openLocationParent(mutation.Location)
	if err != nil {
		return err
	}
	defer unix.Close(parentFD)
	if parent != mutation.Parent {
		return errors.New("target parent identity changed")
	}
	privateFD, _, err := openPrivateAt(
		parentFD, mutation.Private.Name, mutation.Private.Identity,
	)
	if isMissing(err) {
		return workspace.verifyParentIdentity(mutation)
	}
	if err != nil {
		return err
	}
	defer unix.Close(privateFD)
	empty, err := directoryEmpty(privateFD)
	if err != nil {
		return err
	}
	if !empty {
		return errors.New("private directory is not empty")
	}
	actual, _, err := identityAt(parentFD, mutation.Private.Name)
	if err != nil || actual != mutation.Private.Identity {
		return errors.Join(err, errors.New("private directory identity changed"))
	}
	if err := unix.Unlinkat(parentFD, mutation.Private.Name, unix.AT_REMOVEDIR); err != nil {
		return fmt.Errorf("remove private directory: %w", err)
	}
	return errors.Join(syncDirectory(parentFD), workspace.verifyParentIdentity(mutation))
}

func (workspace Workspace) openMutation(
	mutation executor.WorkspaceMutation,
) (mutationContext, error) {
	if !validFileIdentity(mutation.Parent) ||
		!validFileIdentity(mutation.Private.Identity) {
		return mutationContext{}, errors.New("invalid workspace identity")
	}
	parentFD, final, parent, err := workspace.openLocationParent(mutation.Location)
	if err != nil {
		return mutationContext{}, err
	}
	if parent != mutation.Parent {
		unix.Close(parentFD)
		return mutationContext{}, errors.New("target parent identity changed")
	}
	privateFD, _, err := openPrivateAt(
		parentFD, mutation.Private.Name, mutation.Private.Identity,
	)
	if err != nil {
		unix.Close(parentFD)
		return mutationContext{}, fmt.Errorf("open private directory: %w", err)
	}
	return mutationContext{
		parentFD: parentFD, privateFD: privateFD,
		finalName: final, parent: parent,
	}, nil
}

func (workspace Workspace) verifyParentIdentity(
	mutation executor.WorkspaceMutation,
) error {
	fd, _, identity, err := workspace.openLocationParent(mutation.Location)
	if err != nil {
		return err
	}
	unix.Close(fd)
	if identity != mutation.Parent {
		return errors.New("target parent identity changed")
	}
	return nil
}

func syncRenamedDirectories(sourceFD int, destinationFD int) error {
	return errors.Join(syncDirectory(sourceFD), syncDirectory(destinationFD))
}

func matchesImage(state executor.LinkState, image executor.LinkImage) bool {
	return state.Exists == image.Exists &&
		state.RawTarget == image.RawTarget &&
		state.Entry == image.Entry
}

func installImage(mutation executor.WorkspaceMutation) executor.LinkImage {
	return executor.LinkImage{
		Exists: true, RawTarget: mutation.After.RawTarget,
		Entry: mutation.StagedIdentity,
	}
}

func validFileIdentity(identity executor.FileIdentity) bool {
	return identity.Device != 0 && identity.Inode != 0
}
