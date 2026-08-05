package executor

import (
	"errors"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (executor Executor) prepareWritableFileMigration(
	operation domain.Operation,
	release ReleaseIdentity,
) (JournalMutation, error) {
	if _, err := executor.writableFileMigrationWorkspace(); err != nil {
		return JournalMutation{}, err
	}
	state, err := executor.workspace.Inspect(operation.Artifact.Location)
	if err != nil {
		return JournalMutation{}, err
	}
	before := LinkImage{
		Exists: true, RawTarget: operation.Artifact.RawTarget,
		Entry: fileIdentityFromArtifact(operation.Artifact),
	}
	if stateOf(before, state.Parent) != state {
		return JournalMutation{}, errors.New("managed symlink changed after preview")
	}
	if _, err := executor.readWritableSource(operation); err != nil {
		return JournalMutation{}, err
	}
	mutation := JournalMutation{
		ComponentID: operation.ComponentID, UnitID: operation.UnitID,
		Kind: MutationReplace, Location: operation.Artifact.Location,
		SourcePath: operation.SourcePath, SourceSHA256: operation.SourceSHA256,
		Materialization: domain.MaterializationWritableFile,
		Before:          before,
		FileAfter: ConfigurationFileImage{
			Exists: true, SHA256: operation.SourceSHA256, Mode: writableFileMode,
		},
		Parent: state.Parent, StagedName: "staged", RetainedName: "staged",
		Phase: StepPrepared,
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

func fileIdentityFromArtifact(artifact domain.Artifact) FileIdentity {
	return FileIdentity{
		Device: artifact.LinkDevice, Inode: artifact.LinkInode,
		BirthSeconds:     artifact.LinkBirthSeconds,
		BirthNanoseconds: artifact.LinkBirthNanoseconds,
	}
}

func (executor Executor) writableFileMigrationWorkspace() (WritableFileMigrationWorkspace, error) {
	workspace, ok := executor.configurations.(WritableFileMigrationWorkspace)
	if !ok {
		return nil, errors.New("configuration workspace cannot migrate managed symlink")
	}
	return workspace, nil
}

func (executor Executor) publishWritableFile(step JournalMutation) (ConfigurationState, error) {
	if !writableFileMigration(step) {
		return executor.configurations.PublishConfiguration(writableConfigurationMutation(step))
	}
	workspace, err := executor.writableFileMigrationWorkspace()
	if err != nil {
		return ConfigurationState{}, err
	}
	return workspace.PublishWritableFileMigration(step)
}

func (executor Executor) finalizeWritableFile(
	step JournalMutation,
	mutation JournalConfigurationMutation,
) error {
	if !writableFileMigration(step) {
		return executor.configurations.FinalizeConfiguration(mutation)
	}
	workspace, err := executor.writableFileMigrationWorkspace()
	if err != nil {
		return err
	}
	return workspace.FinalizeWritableFileMigration(step)
}

func writableFileMigration(step JournalMutation) bool {
	return step.Materialization == domain.MaterializationWritableFile && step.Before.Exists
}
