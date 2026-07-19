package executor

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (executor Executor) prepare(
	operation domain.Operation,
	release ReleaseIdentity,
) (JournalMutation, error) {
	if operation.Kind == domain.OperationRelinquish {
		mutation := JournalMutation{
			ComponentID: operation.ComponentID, UnitID: operation.UnitID,
			Kind: MutationRelinquish, Location: operation.Artifact.Location,
			Phase: StepPrepared,
		}
		if err := executor.prepareClaim(&mutation, operation, release); err != nil {
			return JournalMutation{}, err
		}
		return mutation, nil
	}
	before, err := executor.workspace.Inspect(operation.Artifact.Location)
	if err != nil {
		return JournalMutation{}, err
	}
	if err := validateFreshObservation(operation, before); err != nil {
		return JournalMutation{}, err
	}
	target, err := executor.mutationTarget(operation, before)
	if err != nil {
		return JournalMutation{}, err
	}
	mutation, err := newMutation(operation, before, target)
	if err != nil {
		return JournalMutation{}, err
	}
	if err := executor.prepareClaim(&mutation, operation, release); err != nil {
		return JournalMutation{}, err
	}
	if mutation.Kind == MutationRelinquish {
		return mutation, nil
	}
	mutation.Private.Name, err = executor.workspace.AllocatePrivateName()
	return mutation, err
}

func newMutation(
	operation domain.Operation,
	before LinkState,
	target string,
) (JournalMutation, error) {
	mutation := JournalMutation{
		ComponentID: operation.ComponentID, UnitID: operation.UnitID,
		Location: operation.Artifact.Location, SourcePath: operation.SourcePath,
		Before: imageOf(before), Parent: before.Parent, Phase: StepPrepared,
	}
	switch operation.Kind {
	case domain.OperationInstall:
		if before.Exists {
			return JournalMutation{}, errors.New("install target appeared after preview")
		}
		mutation.Kind = MutationInstall
		mutation.After = LinkImage{Exists: true, RawTarget: target}
		mutation.StagedName = "staged"
	case domain.OperationAdopt:
		if !before.Exists {
			return JournalMutation{}, errors.New("adopt target disappeared after preview")
		}
		mutation.Kind = MutationAdopt
		mutation.After = mutation.Before
	case domain.OperationReplace:
		if !before.Exists {
			return JournalMutation{}, errors.New("replace target disappeared after preview")
		}
		mutation.Kind = MutationReplace
		mutation.After = LinkImage{Exists: true, RawTarget: target}
		mutation.StagedName, mutation.RetainedName = "staged", "staged"
	case domain.OperationRemove:
		if !before.Exists || before.RawTarget != target {
			return JournalMutation{}, errors.New("remove target changed after preview")
		}
		mutation.Kind, mutation.RetainedName = MutationRemove, "retained"
	default:
		return JournalMutation{}, fmt.Errorf("unsupported operation %q", operation.Kind)
	}
	return mutation, nil
}

func validateFreshObservation(operation domain.Operation, before LinkState) error {
	if operation.Artifact.LinkDevice == 0 && operation.Artifact.LinkInode == 0 {
		return nil
	}
	expected := FileIdentity{
		Device: operation.Artifact.LinkDevice,
		Inode:  operation.Artifact.LinkInode,
	}
	if !before.Exists || before.RawTarget != operation.Artifact.RawTarget || before.Entry != expected {
		return errors.New("link identity changed after preview")
	}
	return nil
}

func (executor Executor) mutationTarget(
	operation domain.Operation,
	before LinkState,
) (string, error) {
	if operation.Kind == domain.OperationRemove && operation.UnitID != "" {
		return before.RawTarget, nil
	}
	if operation.Kind == domain.OperationAdopt || operation.Kind == domain.OperationRelinquish {
		return "", nil
	}
	return executor.workspace.ResolveSource(operation.SourcePath)
}
