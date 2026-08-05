package executor

import (
	"crypto/sha256"
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

const writableFileMode uint32 = 0o600

type writableSourceReader interface {
	ReadSourceFile(domain.ArtifactPath) ([]byte, error)
}

func (executor Executor) prepareWritableFile(
	operation domain.Operation,
	release ReleaseIdentity,
) (JournalMutation, error) {
	if executor.configurations == nil {
		return JournalMutation{}, errors.New("configuration workspace is required for writable-file mutation")
	}
	if operation.Kind == domain.OperationReplace && operation.Artifact.RawTarget != "" {
		return executor.prepareWritableFileMigration(operation, release)
	}
	state, err := executor.configurations.InspectConfiguration(operation.Artifact.Location)
	if err != nil {
		return JournalMutation{}, err
	}
	if err := validateFreshWritableObservation(operation, state); err != nil {
		return JournalMutation{}, err
	}
	mutation := JournalMutation{
		ComponentID: operation.ComponentID, UnitID: operation.UnitID,
		Kind: mutationKind(operation.Kind), Location: operation.Artifact.Location,
		SourcePath: operation.SourcePath, SourceSHA256: operation.SourceSHA256,
		Materialization: domain.MaterializationWritableFile,
		FileBefore:      configurationImage(state), Parent: state.Parent,
		Phase: StepPrepared,
	}
	if operation.Kind == domain.OperationInstall || operation.Kind == domain.OperationReplace {
		if _, readErr := executor.readWritableSource(operation); readErr != nil {
			return JournalMutation{}, readErr
		}
		mutation.FileAfter = ConfigurationFileImage{
			Exists: true, SHA256: operation.SourceSHA256, Mode: writableFileMode,
		}
		mutation.StagedName = "staged"
		if operation.Kind == domain.OperationReplace {
			mutation.RetainedName = "staged"
		}
	} else if operation.Kind == domain.OperationRemove {
		mutation.StagedName = "staged"
		mutation.RetainedName = "retained"
	}
	mutation.Private.Name, err = executor.workspace.AllocatePrivateName()
	if err != nil {
		return JournalMutation{}, err
	}
	if err := executor.prepareClaim(&mutation, operation, release); err != nil {
		return JournalMutation{}, err
	}
	return mutation, nil
}

func (executor Executor) readWritableSource(operation domain.Operation) ([]byte, error) {
	reader, ok := executor.workspace.(writableSourceReader)
	if !ok {
		return nil, errors.New("workspace cannot read writable-file source")
	}
	payload, err := reader.ReadSourceFile(operation.SourcePath)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(payload)
	if fmt.Sprintf("%x", sum) != operation.SourceSHA256 {
		return nil, errors.New("writable-file source digest differs from preview")
	}
	return payload, nil
}

func mutationKind(kind domain.OperationKind) MutationKind {
	switch kind {
	case domain.OperationInstall:
		return MutationInstall
	case domain.OperationReplace:
		return MutationReplace
	case domain.OperationRemove:
		return MutationRemove
	default:
		return ""
	}
}

func validateFreshWritableObservation(operation domain.Operation, state ConfigurationState) error {
	if operation.Kind == domain.OperationInstall {
		if state.Exists {
			return errors.New("writable-file install target appeared after preview")
		}
		return nil
	}
	expected := configurationImageFromArtifact(operation.Artifact)
	if !configurationStateMatches(state, expected, state.Parent) {
		return errors.New("writable file changed after preview")
	}
	return nil
}

func configurationImage(state ConfigurationState) ConfigurationFileImage {
	if !state.Exists {
		return ConfigurationFileImage{}
	}
	return ConfigurationFileImage{
		Exists: true, SHA256: state.SHA256, Mode: state.Mode, Entry: state.Entry,
	}
}

func configurationImageFromArtifact(artifact domain.Artifact) ConfigurationFileImage {
	if artifact.Ownership == domain.OwnershipManagedMissing {
		return ConfigurationFileImage{}
	}
	return ConfigurationFileImage{
		Exists: true, SHA256: artifact.ContentSHA256, Mode: artifact.Mode,
		Entry: FileIdentity{
			Device: artifact.LinkDevice, Inode: artifact.LinkInode,
			BirthSeconds:     artifact.LinkBirthSeconds,
			BirthNanoseconds: artifact.LinkBirthNanoseconds,
		},
	}
}

func (executor Executor) executeWritableFileStep(journal *Journal, index int) error {
	if err := executor.prepareWritablePrivate(journal, index); err != nil {
		return err
	}
	step := &journal.Steps[index]
	if step.FileAfter.Exists {
		reader := executor.workspace.(writableSourceReader)
		payload, err := reader.ReadSourceFile(step.SourcePath)
		if err != nil {
			return err
		}
		identity, err := executor.configurations.StageConfiguration(
			writableConfigurationMutation(*step), payload,
		)
		if err != nil {
			return err
		}
		step.StagedIdentity = identity
		step.Phase = StepStaged
		if err := executor.store.Save(*journal); err != nil {
			return executor.persistBeforeAbort(journal, err)
		}
	}
	actual, publishErr := executor.publishWritableFile(*step)
	expected := step.FileAfter
	if expected.Exists {
		expected.Entry = step.StagedIdentity
	}
	if !configurationStateMatches(actual, expected, step.Parent) {
		return errors.Join(publishErr, errors.New("confirm writable-file publication"))
	}
	step.FileAfter.Entry = actual.Entry
	step.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, errors.Join(publishErr, err))
	}
	if publishErr != nil {
		return publishErr
	}
	return executor.publishClaim(journal, index)
}

func (executor Executor) prepareWritablePrivate(journal *Journal, index int) error {
	step := &journal.Steps[index]
	identity, err := executor.configurations.PrepareConfigurationPrivate(
		writableConfigurationMutation(*step),
	)
	if err != nil {
		return err
	}
	step.Private.Identity = identity
	return executor.store.Save(*journal)
}

func (executor Executor) adoptWritableFileStage(journal *Journal, index int) error {
	step := &journal.Steps[index]
	if step.Phase != StepPrepared {
		return nil
	}
	identity, exists, err := executor.configurations.AdoptStagedConfiguration(
		writableConfigurationMutation(*step),
	)
	if err != nil {
		return err
	}
	if !exists {
		if err := executor.configurations.FinalizeConfigurationPrivate(
			writableConfigurationMutation(*step),
		); err != nil {
			return err
		}
		step.Phase = StepRolledBack
		step.Finalized = true
		return executor.store.Save(*journal)
	}
	if step.FileAfter.Exists {
		if !validFileIdentity(identity) {
			return errors.New("adopted writable-file stage has invalid identity")
		}
		step.StagedIdentity = identity
		step.Phase = StepStaged
	} else {
		if identity != (FileIdentity{}) {
			return errors.New("adopted writable-file removal has staged identity")
		}
		step.Phase = StepPublished
	}
	return executor.store.Save(*journal)
}

func writableConfigurationMutation(step JournalMutation) JournalConfigurationMutation {
	return JournalConfigurationMutation{
		Disposition: ConfigurationPresent,
		Target:      step.Location, Before: step.FileBefore, After: step.FileAfter,
		Parent: step.Parent, Private: step.Private, StagedName: step.StagedName,
		StagedIdentity: step.StagedIdentity, Phase: step.Phase, Finalized: step.Finalized,
	}
}

func (executor Executor) finalizeWritableFileStep(journal *Journal, index int) error {
	step := &journal.Steps[index]
	mutation := writableConfigurationMutation(*step)
	if !step.Finalized {
		if err := executor.finalizeWritableFile(*step, mutation); err != nil {
			return err
		}
		step.Finalized = true
		if err := executor.store.Save(*journal); err != nil {
			return err
		}
	}
	return executor.configurations.FinalizeConfigurationPrivate(
		writableConfigurationMutation(*step),
	)
}

func validateWritableFileStep(step JournalMutation) error {
	if !step.Before.Exists && !step.After.Exists && step.FileBefore.IsZero() && step.FileAfter.IsZero() {
		return errors.New("writable-file step has no file image")
	}
	migration := writableFileMigration(step)
	if (!migration && (step.Before.Exists || step.After.Exists)) ||
		(migration && (!validImage(step.Before) || !step.Before.Exists || step.After.Exists)) {
		return errors.New("writable-file step contains link images")
	}
	if !validFileIdentity(step.Parent) || !privateNamePattern.MatchString(step.Private.Name) ||
		(step.Private.Identity != (FileIdentity{}) && !validFileIdentity(step.Private.Identity)) {
		return errors.New("invalid writable-file workspace")
	}
	if step.Phase != StepPrepared && !validFileIdentity(step.Private.Identity) {
		return errors.New("missing writable-file private identity")
	}
	if step.Finalized && step.Phase != StepPublished && step.Phase != StepRolledBack {
		return errors.New("invalid finalized writable-file phase")
	}
	if !validWritableImage(step.FileBefore) || !validWritableImage(step.FileAfter) {
		return errors.New("invalid writable-file image")
	}
	switch step.Kind {
	case MutationInstall:
		if step.FileBefore.Exists || !step.FileAfter.Exists || step.StagedName != "staged" ||
			step.RetainedName != "" || step.SourceSHA256 != step.FileAfter.SHA256 {
			return errors.New("invalid writable-file install")
		}
	case MutationReplace:
		if ((!migration && (!step.FileBefore.Exists || !validFileIdentity(step.FileBefore.Entry))) ||
			(migration && !step.FileBefore.IsZero())) ||
			!step.FileAfter.Exists || step.StagedName != "staged" || step.RetainedName != "staged" ||
			step.SourceSHA256 != step.FileAfter.SHA256 {
			return errors.New("invalid writable-file replace")
		}
	case MutationRemove:
		if !step.FileBefore.Exists || step.FileAfter.Exists || step.StagedName != "staged" ||
			!validFileIdentity(step.FileBefore.Entry) || step.RetainedName != "retained" ||
			step.SourceSHA256 != "" {
			return errors.New("invalid writable-file removal")
		}
	default:
		return errors.New("invalid writable-file mutation kind")
	}
	if step.Phase == StepStaged && !validFileIdentity(step.StagedIdentity) {
		return errors.New("missing writable-file staged identity")
	}
	if step.Phase == StepPublished && step.FileAfter.Exists &&
		(!validFileIdentity(step.StagedIdentity) || step.FileAfter.Entry != step.StagedIdentity) {
		return errors.New("published writable-file identity mismatch")
	}
	if err := validateWritableFileClaims(step); err != nil {
		return err
	}
	return nil
}

func validateWritableFileClaims(step JournalMutation) error {
	if writableFileMigration(step) && step.ClaimBefore != nil &&
		(step.ClaimBefore.Materialization == domain.MaterializationWritableFile ||
			step.ClaimBefore.RawTarget != step.Before.RawTarget) {
		return errors.New("writable-file migration claim differs from link image")
	}
	for _, pair := range []struct {
		claim *linkownership.Claim
		image ConfigurationFileImage
	}{{step.ClaimBefore, step.FileBefore}, {step.ClaimAfter, step.FileAfter}} {
		if pair.claim == nil || !pair.image.Exists {
			continue
		}
		if pair.claim.Materialization != domain.MaterializationWritableFile ||
			pair.claim.ContentSHA256 != pair.image.SHA256 || pair.claim.Mode != pair.image.Mode {
			return errors.New("writable-file claim differs from file image")
		}
	}
	return nil
}

func validWritableImage(image ConfigurationFileImage) bool {
	if !image.Exists {
		return image.IsZero()
	}
	return digestPattern.MatchString(image.SHA256) && image.Mode == writableFileMode &&
		(image.Entry == (FileIdentity{}) || validFileIdentity(image.Entry))
}

func journalHasWritableFiles(journal Journal) bool {
	for _, step := range journal.Steps {
		if step.Materialization == domain.MaterializationWritableFile {
			return true
		}
	}
	return false
}
