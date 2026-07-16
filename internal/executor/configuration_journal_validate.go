package executor

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func validateJournalSchema(journal Journal) error {
	if journal.SchemaVersion == CurrentJournalSchemaVersion {
		return nil
	}
	return fmt.Errorf("invalid journal schema version %d", journal.SchemaVersion)
}

func validateJournalConfigurations(
	transitions []JournalConfigurationTransition,
	status TransactionStatus,
	privateNames map[string]bool,
) ([]domain.Location, error) {
	var locations []domain.Location
	resourceIDs := make(map[string]bool)
	for index, transition := range transitions {
		if err := validateConfigurationResourceIDs(
			transition.ResourceIDs,
			resourceIDs,
		); err != nil {
			return nil, fmt.Errorf("invalid configuration %d: %w", index, err)
		}
		if len(transition.Mutations) == 0 {
			return nil, fmt.Errorf("invalid configuration %d: mutations must not be empty", index)
		}
		for mutationIndex, mutation := range transition.Mutations {
			if err := validateJournalConfigurationMutation(mutation); err != nil {
				return nil, fmt.Errorf(
					"invalid configuration %d mutation %d: %w",
					index,
					mutationIndex,
					err,
				)
			}
			if privateNames[mutation.Private.Name] {
				return nil, fmt.Errorf(
					"duplicate private name %q",
					mutation.Private.Name,
				)
			}
			privateNames[mutation.Private.Name] = true
			if status == TransactionCommitted && mutation.Phase != StepPublished {
				return nil, fmt.Errorf(
					"committed transaction has non-applied configuration",
				)
			}
			locations = append(locations, mutation.Target)
		}
	}
	return locations, nil
}

func validateConfigurationResourceIDs(
	identifiers []string,
	seen map[string]bool,
) error {
	if len(identifiers) == 0 {
		return fmt.Errorf("resource IDs must not be empty")
	}
	for _, identifier := range identifiers {
		if !identityPattern.MatchString(identifier) || seen[identifier] {
			return fmt.Errorf("invalid duplicate resource ID %q", identifier)
		}
		seen[identifier] = true
	}
	return nil
}

func validateJournalConfigurationMutation(
	mutation JournalConfigurationMutation,
) error {
	if !validLocation(mutation.Target) {
		return fmt.Errorf("invalid target")
	}
	if !validStepPhase(mutation.Phase) {
		return fmt.Errorf("invalid phase %q", mutation.Phase)
	}
	if !privateNamePattern.MatchString(mutation.Private.Name) ||
		mutation.StagedName != "staged" {
		return fmt.Errorf("invalid private workspace")
	}
	if err := validateConfigurationBeforeImage(mutation.Before); err != nil {
		return fmt.Errorf("invalid before image: %w", err)
	}
	if err := validateConfigurationAfterImage(mutation.After); err != nil {
		return fmt.Errorf("invalid after image: %w", err)
	}
	if !validOptionalIdentity(mutation.Parent) ||
		!validOptionalIdentity(mutation.Private.Identity) {
		return fmt.Errorf("invalid workspace identity")
	}
	return validateConfigurationPhase(mutation)
}

func validateConfigurationBeforeImage(image ConfigurationFileImage) error {
	if !image.Exists {
		if image.SHA256 != "" || image.Mode != 0 || image.Entry != (FileIdentity{}) {
			return fmt.Errorf("absent image has metadata")
		}
		return nil
	}
	if !digestPattern.MatchString(image.SHA256) ||
		image.Mode > 0o777 ||
		image.Mode&0o400 == 0 ||
		!validFileIdentity(image.Entry) {
		return fmt.Errorf("existing image metadata is invalid")
	}
	return nil
}

func validateConfigurationAfterImage(image ConfigurationFileImage) error {
	if !image.Exists ||
		!digestPattern.MatchString(image.SHA256) ||
		image.Mode&0o400 == 0 ||
		image.Mode & ^uint32(0o600) != 0 ||
		!validOptionalIdentity(image.Entry) {
		return fmt.Errorf("published image metadata is invalid")
	}
	return nil
}

func validateConfigurationPhase(mutation JournalConfigurationMutation) error {
	if mutation.Finalized &&
		mutation.Phase != StepPublished &&
		mutation.Phase != StepRolledBack {
		return fmt.Errorf("invalid finalized phase")
	}
	if mutation.Phase == StepPrepared {
		if mutation.Parent != (FileIdentity{}) ||
			mutation.Private.Identity != (FileIdentity{}) ||
			mutation.StagedIdentity != (FileIdentity{}) ||
			mutation.After.Entry != (FileIdentity{}) {
			return fmt.Errorf("prepared mutation has runtime identity")
		}
		return nil
	}
	if mutation.Phase == StepParentBound {
		if !validFileIdentity(mutation.Parent) ||
			mutation.Private.Identity != (FileIdentity{}) ||
			mutation.StagedIdentity != (FileIdentity{}) ||
			mutation.After.Entry != (FileIdentity{}) {
			return fmt.Errorf("parent-bound mutation has invalid identity")
		}
		return nil
	}
	if mutation.Phase == StepRolledBack && mutation.Finalized &&
		mutation.Private.Identity == (FileIdentity{}) {
		if mutation.StagedIdentity != (FileIdentity{}) ||
			mutation.After.Entry != (FileIdentity{}) {
			return fmt.Errorf("pre-private rollback has staged identity")
		}
		return nil
	}
	if !validFileIdentity(mutation.Parent) ||
		!validFileIdentity(mutation.Private.Identity) {
		return fmt.Errorf("later phase lacks exact identities")
	}
	if mutation.Phase == StepPrivateCreated {
		if mutation.StagedIdentity != (FileIdentity{}) ||
			mutation.After.Entry != (FileIdentity{}) {
			return fmt.Errorf("private-created mutation has staged identity")
		}
		return nil
	}
	if !validFileIdentity(mutation.StagedIdentity) {
		return fmt.Errorf("later phase lacks staged identity")
	}
	if mutation.After.Entry != (FileIdentity{}) &&
		mutation.After.Entry != mutation.StagedIdentity {
		return fmt.Errorf("after identity differs from staged identity")
	}
	if mutation.Phase == StepStaged && mutation.After.Entry != (FileIdentity{}) {
		return fmt.Errorf("staged mutation has published identity")
	}
	if mutation.Phase == StepPublished &&
		mutation.After.Entry != mutation.StagedIdentity {
		return fmt.Errorf("published identity mismatch")
	}
	return nil
}

func validOptionalIdentity(identity FileIdentity) bool {
	return identity == (FileIdentity{}) || validFileIdentity(identity)
}
