package executor

import (
	"fmt"
	"path"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

var identityPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var privateNamePattern = regexp.MustCompile(`^\.mainframe-[0-9a-f]{32}$`)

func validatePreview(preview Preview) error {
	if !validRelease(preview.Release) {
		return fmt.Errorf("invalid release identity")
	}
	if err := validateDesired(preview.Desired); err != nil {
		return err
	}
	if err := validateOperations(preview.Plan.Operations); err != nil {
		return err
	}
	return validatePreparedTargets(
		preview.Configuration.Transitions(),
		preview.Plan.Operations,
	)
}

func validateDesired(desired []domain.ComponentID) error {
	seenComponents := make(map[domain.ComponentID]bool)
	for _, component := range desired {
		if !identityPattern.MatchString(string(component)) || seenComponents[component] {
			return fmt.Errorf("invalid duplicate desired component %q", component)
		}
		seenComponents[component] = true
	}
	return nil
}

func validateOperations(operations []domain.Operation) error {
	locations := make([]domain.Location, 0, len(operations))
	for _, operation := range operations {
		if operation.Kind == domain.OperationConflict {
			return fmt.Errorf("plan contains conflict at %v", operation.Artifact.Location)
		}
		if operation.Kind != domain.OperationInstall &&
			operation.Kind != domain.OperationAdopt &&
			operation.Kind != domain.OperationReplace &&
			operation.Kind != domain.OperationRemove &&
			operation.Kind != domain.OperationRelinquish {
			return fmt.Errorf("plan contains unsupported operation %q", operation.Kind)
		}
		if !identityPattern.MatchString(string(operation.ComponentID)) ||
			!validLocation(operation.Artifact.Location) {
			return fmt.Errorf("plan contains invalid operation %#v", operation)
		}
		needsSource := operation.Kind == domain.OperationInstall ||
			operation.Kind == domain.OperationReplace || operation.UnitID == ""
		if needsSource && !validRelative(string(operation.SourcePath)) {
			return fmt.Errorf("plan contains invalid source %q", operation.SourcePath)
		}
		if operation.UnitID != "" && !identityPattern.MatchString(operation.UnitID) {
			return fmt.Errorf("plan contains invalid unit ID %q", operation.UnitID)
		}
		if (operation.Kind == domain.OperationAdopt ||
			operation.Kind == domain.OperationReplace ||
			operation.Kind == domain.OperationRelinquish) && operation.UnitID == "" {
			return fmt.Errorf("plan operation %q requires a stable unit ID", operation.Kind)
		}
		if operation.Artifact.UnitID != "" && operation.Artifact.UnitID != operation.UnitID {
			return fmt.Errorf("plan operation unit differs from observed artifact")
		}
		if operation.Kind == domain.OperationRemove &&
			!operation.Artifact.Ownership.Removable() {
			return fmt.Errorf("remove operation is not exact managed ownership")
		}
		if operation.Kind == domain.OperationReplace &&
			operation.Artifact.Ownership != domain.OwnershipManagedPrevious {
			return fmt.Errorf("replace operation is not a previous managed release")
		}
		if operation.Kind == domain.OperationAdopt &&
			operation.Artifact.Ownership != domain.OwnershipExactAdoptable {
			return fmt.Errorf("adopt operation is not an exact unclaimed link")
		}
		if operation.Kind == domain.OperationRelinquish &&
			operation.Artifact.Ownership != domain.OwnershipManagedDrifted &&
			operation.Artifact.Ownership != domain.OwnershipManagedMissing {
			return fmt.Errorf("relinquish operation is not a drifted or missing claim")
		}
		locations = append(locations, operation.Artifact.Location)
	}
	return validateDistinctLocations(locations)
}

func validateJournal(journal Journal) error {
	return validateJournalVersion(journal, CurrentJournalSchemaVersion)
}

func validateJournalVersion(journal Journal, schemaVersion int) error {
	if err := validateJournalHeader(journal, schemaVersion); err != nil {
		return err
	}
	locations := make([]domain.Location, 0, len(journal.Steps))
	privateNames := make(map[string]bool)
	for _, directory := range journal.Directories {
		privateNames[directory.PrivateName] = true
	}
	configurationLocations, err := validateJournalConfigurations(
		journal.Configurations,
		journal.Status,
		privateNames,
	)
	if err != nil {
		return err
	}
	locations = append(locations, configurationLocations...)
	for index, step := range journal.Steps {
		if err := validateJournalStep(step); err != nil {
			return fmt.Errorf("invalid step %d: %w", index, err)
		}
		if !stepMatchesOperation(step, journal.Plan.Operations[index]) {
			return fmt.Errorf("step %d does not match the saved plan", index)
		}
		if step.Private.Name != "" {
			if privateNames[step.Private.Name] {
				return fmt.Errorf("duplicate private name %q", step.Private.Name)
			}
			privateNames[step.Private.Name] = true
		}
		if journal.Status == TransactionCommitted && step.Phase != StepPublished {
			return fmt.Errorf("committed transaction has non-applied step %d", index)
		}
		if journal.Status == TransactionCommitted && step.UnitID != "" &&
			step.ClaimPhase != ClaimPublished {
			return fmt.Errorf("committed transaction has unpublished claim %d", index)
		}
		locations = append(locations, step.Location)
	}
	return validateDistinctLocations(locations)
}

func validateJournalHeader(journal Journal, schemaVersion int) error {
	if err := validateJournalSchemaVersion(journal, schemaVersion); err != nil {
		return err
	}
	if !validRelease(journal.Release) {
		return fmt.Errorf("invalid release identity")
	}
	if err := validateDesired(journal.Desired); err != nil {
		return err
	}
	if err := validateOperations(journal.Plan.Operations); err != nil {
		return fmt.Errorf("invalid journal plan: %w", err)
	}
	if journal.Status != TransactionInProgress && journal.Status != TransactionCommitted {
		return fmt.Errorf("invalid transaction status %q", journal.Status)
	}
	if err := validateJournalDirectories(journal); err != nil {
		return err
	}
	if len(journal.Steps) > len(journal.Plan.Operations) ||
		(journal.Status == TransactionCommitted &&
			len(journal.Steps) != len(journal.Plan.Operations)) {
		return fmt.Errorf("journal steps do not match the saved plan")
	}
	return nil
}

func stepMatchesOperation(step JournalMutation, operation domain.Operation) bool {
	if step.Location != operation.Artifact.Location ||
		step.SourcePath != operation.SourcePath ||
		step.UnitID != operation.UnitID ||
		(step.ComponentID != "" && step.ComponentID != operation.ComponentID) {
		return false
	}
	return operation.Kind == domain.OperationInstall && step.Kind == MutationInstall ||
		operation.Kind == domain.OperationAdopt && step.Kind == MutationAdopt ||
		operation.Kind == domain.OperationReplace && step.Kind == MutationReplace ||
		operation.Kind == domain.OperationRemove && step.Kind == MutationRemove ||
		operation.Kind == domain.OperationRelinquish && step.Kind == MutationRelinquish
}

func validRelease(release ReleaseIdentity) bool {
	return identityPattern.MatchString(release.ID) &&
		digestPattern.MatchString(release.IndexSHA256)
}

func validateJournalStep(step JournalMutation) error {
	if !validLocation(step.Location) {
		return fmt.Errorf("invalid location")
	}
	if !validLinkStepPhase(step.Phase) {
		return fmt.Errorf("invalid step phase %q", step.Phase)
	}
	if !validImage(step.Before) || !validImage(step.After) {
		return fmt.Errorf("invalid link image")
	}
	if err := validateStepClaims(step); err != nil {
		return err
	}
	if claimOnlyMutation(step.Kind) {
		return validateClaimOnlyStep(step)
	}
	if step.Parent.Device == 0 || step.Parent.Inode == 0 {
		return fmt.Errorf("invalid parent identity")
	}
	if !privateNamePattern.MatchString(step.Private.Name) ||
		(step.Private.Identity != (FileIdentity{}) && !validFileIdentity(step.Private.Identity)) {
		return fmt.Errorf("invalid private directory")
	}
	if step.Phase != StepPrepared && !validFileIdentity(step.Private.Identity) {
		return fmt.Errorf("missing private directory identity")
	}
	if step.Finalized && step.Phase != StepPublished && step.Phase != StepRolledBack {
		return fmt.Errorf("invalid finalized phase")
	}
	switch step.Kind {
	case MutationInstall:
		if err := validateInstallStep(step); err != nil {
			return fmt.Errorf("invalid install mutation")
		}
	case MutationReplace:
		if err := validateReplaceStep(step); err != nil {
			return fmt.Errorf("invalid replace mutation")
		}
	case MutationRemove:
		if err := validateRemoveStep(step); err != nil {
			return fmt.Errorf("invalid remove mutation")
		}
	default:
		return fmt.Errorf("invalid mutation kind %q", step.Kind)
	}
	return nil
}

func validateReplaceStep(step JournalMutation) error {
	if !validRelative(string(step.SourcePath)) || !step.Before.Exists ||
		!step.After.Exists || !validFileIdentity(step.Before.Entry) ||
		step.StagedName != "staged" || step.RetainedName != "staged" {
		return fmt.Errorf("invalid replace fields")
	}
	if step.Phase == StepPrepared {
		return nil
	}
	if !validFileIdentity(step.StagedIdentity) {
		return fmt.Errorf("missing staged identity")
	}
	if step.Phase == StepPublished && step.After.Entry != step.StagedIdentity {
		return fmt.Errorf("published identity mismatch")
	}
	return nil
}

func validStepPhase(phase StepPhase) bool {
	return phase == StepPrepared || phase == StepStaged ||
		phase == StepPublished || phase == StepRolledBack ||
		phase == StepParentBound || phase == StepPrivateCreated
}

func validLinkStepPhase(phase StepPhase) bool {
	return phase == StepPrepared || phase == StepStaged ||
		phase == StepPublished || phase == StepRolledBack
}

func validateInstallStep(step JournalMutation) error {
	if !validRelative(string(step.SourcePath)) || step.Before.Exists ||
		!step.After.Exists || step.StagedName != "staged" ||
		step.RetainedName != "" {
		return fmt.Errorf("invalid install fields")
	}
	if step.Phase == StepPrepared {
		if step.StagedIdentity != (FileIdentity{}) || step.After.Entry != (FileIdentity{}) {
			return fmt.Errorf("prepared install has staged identity")
		}
		return nil
	}
	if !validFileIdentity(step.StagedIdentity) {
		return fmt.Errorf("missing staged identity")
	}
	if step.After.Entry != (FileIdentity{}) && step.After.Entry != step.StagedIdentity {
		return fmt.Errorf("after identity differs from staged identity")
	}
	if step.Phase == StepPublished &&
		(step.After.Entry != step.StagedIdentity || !validFileIdentity(step.After.Entry)) {
		return fmt.Errorf("published identity mismatch")
	}
	return nil
}

func validateRemoveStep(step JournalMutation) error {
	if (step.UnitID == "" && !validRelative(string(step.SourcePath))) || step.After.Exists ||
		!step.Before.Exists || !validFileIdentity(step.Before.Entry) ||
		step.StagedName != "" || step.StagedIdentity != (FileIdentity{}) ||
		step.RetainedName != "retained" || step.Phase == StepStaged {
		return fmt.Errorf("invalid remove fields")
	}
	return nil
}

func validImage(image LinkImage) bool {
	if !image.Exists {
		return image.RawTarget == "" && image.Entry == (FileIdentity{})
	}
	return validText(image.RawTarget) &&
		(image.Entry == (FileIdentity{}) || validFileIdentity(image.Entry))
}

func validText(value string) bool {
	if value == "" || !utf8.ValidString(value) {
		return false
	}
	for _, character := range value {
		if unicode.IsControl(character) {
			return false
		}
	}
	return true
}

func validLocation(location domain.Location) bool {
	return location.Root.Valid() && validRelative(string(location.Path))
}

func validRelative(value string) bool {
	return validText(value) && value != "." && value != ".." &&
		!strings.HasPrefix(value, "../") && !path.IsAbs(value) &&
		path.Clean(value) == value && !strings.ContainsRune(value, '\\')
}

func validateDistinctLocations(locations []domain.Location) error {
	for left, location := range locations {
		for right := left + 1; right < len(locations); right++ {
			other := locations[right]
			if location.Root != other.Root {
				continue
			}
			first, second := string(location.Path), string(other.Path)
			if first == second || strings.HasPrefix(first, second+"/") || strings.HasPrefix(second, first+"/") {
				return fmt.Errorf("duplicate or overlapping locations %v and %v", location, other)
			}
		}
	}
	return nil
}
