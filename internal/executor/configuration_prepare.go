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
	seenTargets map[domain.Location]bool
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
		payloads:    make(map[domain.Location][]byte),
		seenTargets: make(map[domain.Location]bool),
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
		if result.seenTargets[mutation.Target] {
			return JournalConfigurationTransition{}, fmt.Errorf(
				"duplicate configuration target %v",
				mutation.Target,
			)
		}
		result.seenTargets[mutation.Target] = true
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
		if mutation.After.Exists {
			result.payloads[mutation.Target] = append(
				[]byte(nil),
				mutation.After.Content...,
			)
		}
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
				Device:           mutation.Before.Device,
				Inode:            mutation.Before.Inode,
				BirthSeconds:     mutation.Before.BirthSeconds,
				BirthNanoseconds: mutation.Before.BirthNanoseconds,
			},
		}
	}
	after := ConfigurationFileImage{}
	if mutation.After.Exists {
		sum := sha256.Sum256(mutation.After.Content)
		after = ConfigurationFileImage{
			Exists: true,
			SHA256: fmt.Sprintf("%x", sum),
			Mode:   mutation.After.Mode,
		}
	}
	return JournalConfigurationMutation{
		Disposition: journalConfigurationDisposition(mutation.Disposition),
		Target:      mutation.Target,
		Before:      before,
		After:       after,
		Private:     PrivateDirectory{Name: privateName},
		StagedName:  "staged",
		Phase:       StepPrepared,
	}
}

func journalConfigurationDisposition(
	disposition configuration.MutationDisposition,
) ConfigurationMutationDisposition {
	if disposition == configuration.MutationRemoveExactDocument {
		return ConfigurationRemoveExactDocument
	}
	if disposition == configuration.MutationPresent {
		return ConfigurationPresent
	}
	return ""
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
			if !validLocation(mutation.Target) {
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
