package executor

import (
	"errors"
	"fmt"
)

func configurationPrivateRequired(
	transitions []JournalConfigurationTransition,
) bool {
	for _, transition := range transitions {
		for _, mutation := range transition.Mutations {
			if mutation.Phase == StepParentBound {
				return true
			}
		}
	}
	return false
}

func (executor Executor) rollbackConfigurations(journal *Journal) error {
	for transition := len(journal.Configurations) - 1; transition >= 0; transition-- {
		mutations := journal.Configurations[transition].Mutations
		for index := len(mutations) - 1; index >= 0; index-- {
			if err := executor.rollbackConfiguration(
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

func (executor Executor) rollbackConfiguration(
	journal *Journal,
	transition int,
	index int,
) error {
	mutation := &journal.Configurations[transition].Mutations[index]
	if mutation.Finalized {
		return executor.finalizeConfigurationWorkspace(*mutation)
	}
	if mutation.Phase == StepPrepared {
		mutation.Phase = StepRolledBack
		mutation.Finalized = true
		return executor.store.Save(*journal)
	}
	if mutation.Phase == StepParentBound {
		if err := executor.prepareConfigurationPrivate(
			journal,
			transition,
			index,
		); err != nil {
			return err
		}
	}
	if mutation.Phase == StepPrivateCreated {
		if err := executor.adoptStagedConfiguration(journal, mutation); err != nil {
			return err
		}
		if mutation.Phase == StepPrivateCreated {
			return executor.finalizeEmptyConfiguration(journal, mutation)
		}
	}
	if mutation.Phase != StepRolledBack {
		if err := executor.configurations.RollbackConfiguration(*mutation); err != nil {
			return fmt.Errorf("rollback configuration %v: %w", mutation.Target, err)
		}
		mutation.Phase = StepRolledBack
		if err := executor.store.Save(*journal); err != nil {
			return fmt.Errorf("save rolled back configuration: %w", err)
		}
	}
	return executor.finalizeRolledBackConfiguration(journal, mutation)
}

func (executor Executor) adoptStagedConfiguration(
	journal *Journal,
	mutation *JournalConfigurationMutation,
) error {
	identity, exists, err := executor.configurations.AdoptStagedConfiguration(
		*mutation,
	)
	if err != nil {
		return fmt.Errorf("adopt staged configuration %v: %w", mutation.Target, err)
	}
	if !exists {
		return nil
	}
	if !validFileIdentity(identity) {
		return errors.New("adopted configuration identity is invalid")
	}
	mutation.StagedIdentity = identity
	mutation.Phase = StepStaged
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save adopted configuration: %w", err)
	}
	return nil
}

func (executor Executor) finalizeEmptyConfiguration(
	journal *Journal,
	mutation *JournalConfigurationMutation,
) error {
	mutation.Phase = StepRolledBack
	mutation.Finalized = true
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save finalized empty configuration: %w", err)
	}
	return executor.finalizeConfigurationWorkspace(*mutation)
}

func (executor Executor) finalizeRolledBackConfiguration(
	journal *Journal,
	mutation *JournalConfigurationMutation,
) error {
	if err := executor.configurations.FinalizeConfiguration(*mutation); err != nil {
		return fmt.Errorf("finalize configuration %v: %w", mutation.Target, err)
	}
	mutation.Finalized = true
	if err := executor.store.Save(*journal); err != nil {
		return fmt.Errorf("save finalized configuration: %w", err)
	}
	return executor.finalizeConfigurationWorkspace(*mutation)
}

func (executor Executor) finalizeCommittedConfigurations(
	journal *Journal,
) error {
	for transition := range journal.Configurations {
		for index := range journal.Configurations[transition].Mutations {
			mutation := &journal.Configurations[transition].Mutations[index]
			if !mutation.Finalized {
				if err := executor.configurations.FinalizeConfiguration(
					*mutation,
				); err != nil {
					return fmt.Errorf(
						"finalize committed configuration %v: %w",
						mutation.Target,
						err,
					)
				}
				mutation.Finalized = true
				if err := executor.store.Save(*journal); err != nil {
					return fmt.Errorf("save finalized configuration: %w", err)
				}
			}
			if err := executor.finalizeConfigurationWorkspace(*mutation); err != nil {
				return err
			}
		}
	}
	return nil
}

func (executor Executor) finalizeConfigurationWorkspace(
	mutation JournalConfigurationMutation,
) error {
	if mutation.Private.Identity == (FileIdentity{}) {
		return nil
	}
	if err := executor.configurations.FinalizeConfigurationPrivate(
		mutation,
	); err != nil {
		return fmt.Errorf(
			"finalize configuration workspace %v: %w",
			mutation.Target,
			err,
		)
	}
	return nil
}
