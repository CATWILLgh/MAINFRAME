package executor

import (
	"errors"
	"fmt"
)

func (executor Executor) allocateDirectoryIntents(
	journal *Journal,
	requirements []DirectoryRequirement,
) error {
	for _, requirement := range requirements {
		name, err := executor.workspace.AllocatePrivateName()
		if err != nil {
			return err
		}
		journal.Directories = append(journal.Directories, JournalDirectory{
			Target:      requirement.Target,
			Mode:        requirement.Mode,
			PrivateName: name,
			Phase:       StepPrepared,
		})
	}
	return validateJournal(*journal)
}

func (executor Executor) executeDirectory(journal *Journal, index int) error {
	directory := &journal.Directories[index]
	state, err := executor.workspace.InspectDirectory(directoryMutation(*journal, *directory))
	if err != nil {
		return fmt.Errorf("inspect managed directory: %w", err)
	}
	if state.Exists || !validFileIdentity(state.Parent) ||
		state.Entry != (FileIdentity{}) || state.Mode != 0 {
		return errors.New("managed directory appeared or has invalid absent state")
	}
	directory.Parent = state.Parent
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(
			journal,
			fmt.Errorf("save managed directory parent identity: %w", err),
		)
	}
	identity, err := executor.workspace.StageDirectory(directoryMutation(*journal, *directory))
	if err != nil {
		return fmt.Errorf("stage managed directory: %w", err)
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a managed directory without identity")
	}
	directory.Entry = identity
	directory.Phase = StepStaged
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(
			journal,
			fmt.Errorf("save staged managed directory identity: %w", err),
		)
	}
	actual, publishErr := executor.workspace.PublishDirectory(
		directoryMutation(*journal, *directory),
	)
	if err := confirmPublishedDirectory(*directory, actual); err != nil {
		return errors.Join(publishErr, fmt.Errorf("confirm managed directory: %w", err))
	}
	directory.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(
			journal,
			errors.Join(publishErr, fmt.Errorf("save published managed directory: %w", err)),
		)
	}
	if publishErr != nil {
		return fmt.Errorf("publish managed directory: %w", publishErr)
	}
	return nil
}

func confirmPublishedDirectory(
	directory JournalDirectory,
	actual DirectoryState,
) error {
	if !actual.Exists || actual.Parent != directory.Parent ||
		actual.Entry != directory.Entry || actual.Mode != directory.Mode {
		return errors.New("workspace returned an unexpected managed directory")
	}
	return nil
}

func directoryMutation(journal Journal, directory JournalDirectory) DirectoryMutation {
	var root RootSnapshot
	for _, candidate := range journal.Roots {
		if candidate.Root == directory.Target.Root {
			root = candidate
			break
		}
	}
	return DirectoryMutation{
		Root:        root,
		Target:      directory.Target,
		Mode:        directory.Mode,
		Parent:      directory.Parent,
		PrivateName: directory.PrivateName,
		Entry:       directory.Entry,
		Phase:       directory.Phase,
	}
}
