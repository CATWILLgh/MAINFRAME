package executor

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (executor Executor) prepareConfigurations(
	journal *Journal,
	payloads map[domain.Location][]byte,
) error {
	if len(journal.Configurations) == 0 {
		return nil
	}
	for transition := range journal.Configurations {
		for mutation := range journal.Configurations[transition].Mutations {
			if err := executor.bindConfigurationParent(
				journal,
				transition,
				mutation,
			); err != nil {
				return err
			}
		}
	}
	for transition := range journal.Configurations {
		for mutation := range journal.Configurations[transition].Mutations {
			if err := executor.prepareConfigurationPrivate(
				journal,
				transition,
				mutation,
			); err != nil {
				return err
			}
		}
	}
	if err := executor.checkAllConfigurationCapabilities(*journal); err != nil {
		return err
	}
	return executor.stageAllConfigurations(journal, payloads)
}

func (executor Executor) bindConfigurationParent(
	journal *Journal,
	transition int,
	index int,
) error {
	mutation := &journal.Configurations[transition].Mutations[index]
	state, err := executor.configurations.InspectConfiguration(mutation.Target)
	if err != nil {
		return fmt.Errorf("inspect configuration %v: %w", mutation.Target, err)
	}
	if !configurationStateMatches(state, mutation.Before, state.Parent) ||
		!validFileIdentity(state.Parent) {
		return fmt.Errorf("configuration %v changed after preview", mutation.Target)
	}
	mutation.Parent = state.Parent
	mutation.Phase = StepParentBound
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save configuration parent: %w", err)
	}
	return nil
}

func (executor Executor) prepareConfigurationPrivate(
	journal *Journal,
	transition int,
	index int,
) error {
	mutation := &journal.Configurations[transition].Mutations[index]
	identity, err := executor.configurations.PrepareConfigurationPrivate(*mutation)
	if err != nil || !validFileIdentity(identity) {
		return errors.Join(
			fmt.Errorf("prepare configuration private workspace: %w", err),
			identityError(identity),
		)
	}
	mutation.Private.Identity = identity
	mutation.Phase = StepPrivateCreated
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save configuration private workspace: %w", err)
	}
	return nil
}

func identityError(identity FileIdentity) error {
	if validFileIdentity(identity) {
		return nil
	}
	return errors.New("configuration workspace returned an invalid identity")
}

func (executor Executor) checkAllConfigurationCapabilities(
	journal Journal,
) error {
	for _, transition := range journal.Configurations {
		for _, mutation := range transition.Mutations {
			if err := executor.configurations.CheckConfigurationCapabilities(
				mutation,
			); err != nil {
				return fmt.Errorf(
					"check configuration capabilities %v: %w",
					mutation.Target,
					err,
				)
			}
		}
	}
	return nil
}

func (executor Executor) stageAllConfigurations(
	journal *Journal,
	payloads map[domain.Location][]byte,
) error {
	for transition := range journal.Configurations {
		for index := range journal.Configurations[transition].Mutations {
			mutation := &journal.Configurations[transition].Mutations[index]
			payload, exists := payloads[mutation.Target]
			if !exists {
				return fmt.Errorf("configuration payload is unavailable")
			}
			identity, err := executor.configurations.StageConfiguration(
				*mutation,
				payload,
			)
			if err != nil {
				return fmt.Errorf("stage configuration %v: %w", mutation.Target, err)
			}
			if !validFileIdentity(identity) {
				return identityError(identity)
			}
			mutation.StagedIdentity = identity
			mutation.Phase = StepStaged
			if err := executor.store.Save(*journal); err != nil {
				return fmt.Errorf("save staged configuration: %w", err)
			}
		}
	}
	return nil
}

func (executor Executor) publishConfigurations(journal *Journal) error {
	for transition := range journal.Configurations {
		for index := range journal.Configurations[transition].Mutations {
			if err := executor.publishConfiguration(
				journal,
				transition,
				index,
			); err != nil {
				return err
			}
		}
	}
	return nil
}

func (executor Executor) publishConfiguration(
	journal *Journal,
	transition int,
	index int,
) error {
	mutation := &journal.Configurations[transition].Mutations[index]
	actual, publishErr := executor.configurations.PublishConfiguration(*mutation)
	expected := mutation.After
	expected.Entry = mutation.StagedIdentity
	if !configurationStateMatches(actual, expected, mutation.Parent) {
		return errors.Join(
			publishErr,
			fmt.Errorf("confirm configuration publication %v", mutation.Target),
		)
	}
	mutation.After.Entry = actual.Entry
	mutation.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return errors.Join(
			publishErr,
			fmt.Errorf("save published configuration: %w", err),
		)
	}
	if publishErr != nil {
		return fmt.Errorf("publish configuration %v: %w", mutation.Target, publishErr)
	}
	return nil
}

func configurationStateMatches(
	state ConfigurationState,
	image ConfigurationFileImage,
	parent FileIdentity,
) bool {
	return state.Exists == image.Exists &&
		state.SHA256 == image.SHA256 &&
		state.Mode == image.Mode &&
		state.Entry == image.Entry &&
		state.Parent == parent
}
