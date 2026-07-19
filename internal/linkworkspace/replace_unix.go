//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func (workspace Workspace) PublishReplace(
	mutation executor.WorkspaceMutation,
) (executor.LinkState, error) {
	if mutation.Kind != executor.MutationReplace ||
		!validFileIdentity(mutation.StagedIdentity) ||
		mutation.StagedName != mutation.RetainedName {
		return executor.LinkState{}, errors.New("invalid replace publication")
	}
	context, err := workspace.openMutation(mutation)
	if err != nil {
		return executor.LinkState{}, err
	}
	defer context.close()
	public, retained, err := inspectReplacePair(context, mutation)
	if err != nil {
		return executor.LinkState{}, err
	}
	if replacePublished(public, retained, mutation) {
		return public, syncRenamedDirectories(context.privateFD, context.parentFD)
	}
	if !replacePrepared(public, retained, mutation) {
		return executor.LinkState{}, errors.New("replace publication state changed")
	}
	if err := renameExchange(
		context.privateFD, mutation.StagedName,
		context.parentFD, context.finalName,
	); err != nil {
		return executor.LinkState{}, fmt.Errorf("publish replace: %w", err)
	}
	syncErr := syncRenamedDirectories(context.privateFD, context.parentFD)
	public, retained, inspectErr := inspectReplacePair(context, mutation)
	if inspectErr == nil && replacePublished(public, retained, mutation) {
		return public, syncErr
	}
	return executor.LinkState{}, errors.Join(
		syncErr, inspectErr, errors.New("replace publication differs"),
	)
}

func inspectReplacePair(
	context mutationContext,
	mutation executor.WorkspaceMutation,
) (executor.LinkState, executor.LinkState, error) {
	public, err := inspectAt(context.parentFD, context.finalName, context.parent)
	if err != nil {
		return executor.LinkState{}, executor.LinkState{}, err
	}
	retained, err := inspectAt(context.privateFD, mutation.StagedName, context.parent)
	return public, retained, err
}

func replacePrepared(public, staged executor.LinkState, mutation executor.WorkspaceMutation) bool {
	after := mutation.After
	after.Entry = mutation.StagedIdentity
	return matchesImage(public, mutation.Before) && matchesImage(staged, after)
}

func replacePublished(public, retained executor.LinkState, mutation executor.WorkspaceMutation) bool {
	after := mutation.After
	after.Entry = mutation.StagedIdentity
	return matchesImage(public, after) && matchesImage(retained, mutation.Before)
}
