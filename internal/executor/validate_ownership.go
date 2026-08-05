package executor

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func validateStepClaims(step JournalMutation) error {
	if step.UnitID == "" {
		if step.ClaimBefore != nil || step.ClaimAfter != nil || step.ClaimPhase != "" {
			return fmt.Errorf("legacy mutation has ownership claim")
		}
		return nil
	}
	if !domain.ValidUnitID(step.UnitID) ||
		!identityPattern.MatchString(string(step.ComponentID)) ||
		(step.ClaimPhase != ClaimPrepared && step.ClaimPhase != ClaimPublished &&
			step.ClaimPhase != ClaimRolledBack) {
		return fmt.Errorf("invalid ownership claim transition")
	}
	claims := make([]linkownership.Claim, 0, 2)
	for _, claim := range []*linkownership.Claim{step.ClaimBefore, step.ClaimAfter} {
		if claim == nil {
			continue
		}
		if claim.UnitID != step.UnitID || claim.ComponentID != step.ComponentID ||
			claim.Target != step.Location {
			return fmt.Errorf("ownership claim differs from mutation")
		}
		claims = append(claims, *claim)
	}
	for _, claim := range claims {
		if _, err := linkownership.New([]linkownership.Claim{claim}); err != nil {
			return fmt.Errorf("invalid ownership claim: %w", err)
		}
	}
	return validateClaimShape(step)
}

func validateClaimShape(step JournalMutation) error {
	switch step.Kind {
	case MutationInstall:
		if step.ClaimAfter == nil {
			return fmt.Errorf("invalid install claim transition")
		}
	case MutationAdopt:
		if step.ClaimBefore != nil || step.ClaimAfter == nil {
			return fmt.Errorf("invalid adopt claim transition")
		}
	case MutationReplace:
		if step.ClaimBefore == nil || step.ClaimAfter == nil {
			return fmt.Errorf("invalid replace claim transition")
		}
	case MutationRemove, MutationRelinquish:
		if step.ClaimBefore == nil || step.ClaimAfter != nil {
			return fmt.Errorf("invalid removal claim transition")
		}
	}
	return nil
}

func validateClaimOnlyStep(step JournalMutation) error {
	if step.Private != (PrivateDirectory{}) ||
		step.StagedName != "" || step.RetainedName != "" ||
		!step.FileBefore.IsZero() || !step.FileAfter.IsZero() || step.SourceSHA256 != "" {
		return fmt.Errorf("invalid claim-only mutation")
	}
	if step.Kind == MutationAdopt {
		if !validFileIdentity(step.Parent) || !step.Before.Exists || step.After != step.Before {
			return fmt.Errorf("adopt mutation changes the link")
		}
	}
	if step.Kind == MutationRelinquish &&
		(step.Parent != (FileIdentity{}) || step.Before.Exists || step.After.Exists) {
		return fmt.Errorf("relinquish mutation keeps a managed link image")
	}
	return nil
}
