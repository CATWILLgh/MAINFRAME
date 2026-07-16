package executor

import (
	"crypto/sha256"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type preparedConfigurations struct {
	transitions []JournalConfigurationTransition
	payloads    map[domain.Location][]byte
	targets     []domain.Location
}

func (executor Executor) materializeConfigurations(
	plan configuration.PreparedPlan,
) (preparedConfigurations, error) {
	transitions := plan.Transitions()
	if len(transitions) > 0 && executor.configurations == nil {
		return preparedConfigurations{}, fmt.Errorf(
			"configuration workspace is required",
		)
	}
	result := preparedConfigurations{
		transitions: make(
			[]JournalConfigurationTransition,
			0,
			len(transitions),
		),
		payloads: make(map[domain.Location][]byte),
	}
	for _, transition := range transitions {
		materialized, err := executor.materializeConfigurationTransition(
			transition,
			&result,
		)
		if err != nil {
			return preparedConfigurations{}, err
		}
		result.transitions = append(result.transitions, materialized)
	}
	return result, nil
}

func (executor Executor) materializeConfigurationTransition(
	transition configuration.Transition,
	result *preparedConfigurations,
) (JournalConfigurationTransition, error) {
	materialized := JournalConfigurationTransition{
		ResourceIDs: append([]string(nil), transition.ResourceIDs...),
		Mutations: make(
			[]JournalConfigurationMutation,
			0,
			len(transition.Mutations),
		),
	}
	for _, mutation := range transition.Mutations {
		if _, exists := result.payloads[mutation.Target]; exists {
			return JournalConfigurationTransition{}, fmt.Errorf(
				"duplicate configuration target %v",
				mutation.Target,
			)
		}
		name, err := executor.workspace.AllocatePrivateName()
		if err != nil {
			return JournalConfigurationTransition{}, fmt.Errorf(
				"allocate configuration private name: %w",
				err,
			)
		}
		journalMutation := journalConfigurationMutation(mutation, name)
		materialized.Mutations = append(
			materialized.Mutations,
			journalMutation,
		)
		result.payloads[mutation.Target] = append([]byte(nil), mutation.After...)
		result.targets = append(result.targets, mutation.Target)
	}
	return materialized, nil
}

func journalConfigurationMutation(
	mutation configuration.FileMutation,
	privateName string,
) JournalConfigurationMutation {
	before := ConfigurationFileImage{}
	if mutation.Before.Exists {
		before = ConfigurationFileImage{
			Exists: true,
			SHA256: mutation.Before.SHA256,
			Mode:   mutation.Before.Mode,
			Entry: FileIdentity{
				Device: mutation.Before.Device,
				Inode:  mutation.Before.Inode,
			},
		}
	}
	sum := sha256.Sum256(mutation.After)
	return JournalConfigurationMutation{
		Target: mutation.Target,
		Before: before,
		After: ConfigurationFileImage{
			Exists: true,
			SHA256: fmt.Sprintf("%x", sum),
			Mode:   mutation.Mode,
		},
		Private:    PrivateDirectory{Name: privateName},
		StagedName: "staged",
		Phase:      StepPrepared,
	}
}

func validatePreparedTargets(
	transitions []configuration.Transition,
	operations []domain.Operation,
) error {
	var locations []domain.Location
	for _, transition := range transitions {
		if len(transition.ResourceIDs) == 0 || len(transition.Mutations) == 0 {
			return fmt.Errorf("prepared configuration transition is empty")
		}
		for _, mutation := range transition.Mutations {
			if !validLocation(mutation.Target) || len(mutation.After) == 0 {
				return fmt.Errorf("prepared configuration mutation is invalid")
			}
			locations = append(locations, mutation.Target)
		}
	}
	for _, operation := range operations {
		locations = append(locations, operation.Artifact.Location)
	}
	return validateDistinctLocations(locations)
}

func directoryPlanningPlan(
	plan domain.Plan,
	configurations []domain.Location,
) domain.Plan {
	result := domain.Plan{
		Operations: append([]domain.Operation(nil), plan.Operations...),
	}
	for _, target := range configurations {
		result.Operations = append(result.Operations, domain.Operation{
			ComponentID: "configuration",
			Kind:        domain.OperationInstall,
			Artifact:    domain.Artifact{Location: target},
			SourcePath:  ".configuration",
		})
	}
	return result
}

func journalConfigurationTargets(
	transitions []JournalConfigurationTransition,
) []domain.Location {
	var result []domain.Location
	for _, transition := range transitions {
		for _, mutation := range transition.Mutations {
			result = append(result, mutation.Target)
		}
	}
	return result
}

func configurationTargetsAsJournal(
	targets []domain.Location,
) []JournalConfigurationTransition {
	if len(targets) == 0 {
		return nil
	}
	mutations := make([]JournalConfigurationMutation, len(targets))
	for index, target := range targets {
		mutations[index].Target = target
	}
	return []JournalConfigurationTransition{{Mutations: mutations}}
}
