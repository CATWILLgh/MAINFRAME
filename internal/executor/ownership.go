package executor

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func (executor Executor) prepareClaim(
	mutation *JournalMutation,
	operation domain.Operation,
	release ReleaseIdentity,
) error {
	if operation.UnitID == "" {
		return nil
	}
	if executor.ownership == nil {
		return errors.New("ownership store is required for claimed mutation")
	}
	registry, err := executor.ownership.LoadOwnership()
	if err != nil {
		return fmt.Errorf("load ownership registry: %w", err)
	}
	before, exists := registry.ClaimAt(operation.Artifact.Location)
	if err := validateClaimBefore(operation, before, exists); err != nil {
		return err
	}
	if exists {
		mutation.ClaimBefore = cloneClaim(&before)
	}
	if operation.Kind == domain.OperationInstall || operation.Kind == domain.OperationAdopt ||
		operation.Kind == domain.OperationReplace {
		mutation.ClaimAfter = &linkownership.Claim{
			UnitID: operation.UnitID, ComponentID: operation.ComponentID,
			Target: operation.Artifact.Location, RawTarget: mutation.After.RawTarget,
			ReleaseID: release.ID, IndexSHA256: release.IndexSHA256,
		}
	}
	mutation.ClaimPhase = ClaimPrepared
	return nil
}

func validateClaimBefore(
	operation domain.Operation,
	before linkownership.Claim,
	exists bool,
) error {
	if operation.Kind == domain.OperationInstall || operation.Kind == domain.OperationAdopt {
		if !exists {
			return nil
		}
		if operation.Kind == domain.OperationInstall &&
			operation.Artifact.Ownership == domain.OwnershipManagedMissing &&
			before.UnitID == operation.UnitID && before.ComponentID == operation.ComponentID &&
			before.RawTarget == operation.Artifact.RawTarget {
			return nil
		}
		return errors.New("install target already has an ownership claim")
	}
	if !exists || before.UnitID != operation.UnitID || before.ComponentID != operation.ComponentID {
		return errors.New("ownership claim changed after preview")
	}
	if operation.Kind == domain.OperationRelinquish {
		if operation.Artifact.Ownership == domain.OwnershipManagedMissing {
			if before.RawTarget != operation.Artifact.RawTarget {
				return errors.New("missing ownership claim changed after preview")
			}
			return nil
		}
		if before.RawTarget == operation.Artifact.RawTarget {
			return errors.New("relinquish requires a changed link target")
		}
		return nil
	}
	if before.RawTarget != operation.Artifact.RawTarget {
		return errors.New("ownership claim target changed after preview")
	}
	return nil
}

func (executor Executor) publishClaim(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if step.ClaimPhase == "" {
		return nil
	}
	if err := executor.verifyAdoptionLink(*step); err != nil {
		return err
	}
	registry, err := executor.ownership.LoadOwnership()
	if err != nil {
		return fmt.Errorf("load ownership registry: %w", err)
	}
	updated, err := transitionRegistry(registry, step.ClaimBefore, step.ClaimAfter)
	if err != nil {
		return err
	}
	if err := executor.ownership.SaveOwnership(updated); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save ownership registry: %w", err))
	}
	if err := executor.verifyAdoptionLink(*step); err != nil {
		return executor.persistBeforeAbort(journal, err)
	}
	step.ClaimPhase = ClaimPublished
	step.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save published ownership claim: %w", err))
	}
	return nil
}

func (executor Executor) verifyAdoptionLink(step JournalMutation) error {
	if step.Kind != MutationAdopt {
		return nil
	}
	actual, err := executor.workspace.Inspect(step.Location)
	if err != nil {
		return fmt.Errorf("inspect adopted link: %w", err)
	}
	if actual != stateOf(step.Before, step.Parent) {
		return errors.New("adopted link changed during ownership publication")
	}
	return nil
}

func transitionRegistry(
	registry linkownership.Registry,
	before *linkownership.Claim,
	after *linkownership.Claim,
) (linkownership.Registry, error) {
	target := claimTarget(before, after)
	if registryMatchesClaim(registry, target, after) {
		return registry, nil
	}
	if !registryMatchesClaim(registry, target, before) {
		return linkownership.Registry{}, errors.New("ownership registry changed during transaction")
	}
	if after == nil {
		updated, _ := registry.Remove(target)
		return updated, nil
	}
	return registry.Put(*after)
}

func registryMatchesClaim(
	registry linkownership.Registry,
	target domain.Location,
	expected *linkownership.Claim,
) bool {
	current, exists := registry.ClaimAt(target)
	if expected == nil {
		return !exists
	}
	return exists && current == *expected
}

func claimTarget(before, after *linkownership.Claim) domain.Location {
	if before != nil {
		return before.Target
	}
	return after.Target
}
