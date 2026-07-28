package configuration

import (
	"fmt"
	"path/filepath"
	"regexp"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

var preparedResourceIDPattern = regexp.MustCompile(
	`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`,
)

var preparedDigestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type PreparedPlan struct {
	transitions      []Transition
	preconditions    []ReadPrecondition
	materializations []SecretMaterializationRecipe
}

func (plan PreparedPlan) Transitions() []Transition {
	result := make([]Transition, len(plan.transitions))
	for index, transition := range plan.transitions {
		result[index] = Transition{
			ResourceIDs:     append([]string(nil), transition.ResourceIDs...),
			PreparationOnly: transition.PreparationOnly,
			Mutations:       cloneFileMutations(transition.Mutations),
		}
	}
	return result
}

func (plan PreparedPlan) Preconditions() []ReadPrecondition {
	return append([]ReadPrecondition(nil), plan.preconditions...)
}

func (plan PreparedPlan) Materializations() []SecretMaterializationRecipe {
	return append(
		[]SecretMaterializationRecipe(nil),
		plan.materializations...,
	)
}

func (plan PreparedPlan) HasPreparationOnly() bool {
	for _, transition := range plan.transitions {
		if transition.PreparationOnly {
			return true
		}
	}
	return false
}

func NewPreparedPlan(transitions []Transition) (PreparedPlan, error) {
	return NewPreparedPlanWithPreconditions(transitions, nil)
}

func NewPreparedPlanWithPreconditions(
	transitions []Transition,
	preconditions []ReadPrecondition,
) (PreparedPlan, error) {
	return NewPreparedPlanWithMaterializations(
		transitions,
		preconditions,
		nil,
	)
}

func NewPreparedPlanWithMaterializations(
	transitions []Transition,
	preconditions []ReadPrecondition,
	materializations []SecretMaterializationRecipe,
) (PreparedPlan, error) {
	normalized := cloneTransitions(transitions)
	if err := validatePreparedTransitions(normalized); err != nil {
		return PreparedPlan{}, err
	}
	normalizedPreconditions := append(
		[]ReadPrecondition(nil),
		preconditions...,
	)
	if err := validateReadPreconditions(
		normalized,
		normalizedPreconditions,
	); err != nil {
		return PreparedPlan{}, err
	}
	normalizedMaterializations := cloneSecretMaterializations(
		materializations,
	)
	if err := validateSecretMaterializations(
		normalized,
		normalizedMaterializations,
	); err != nil {
		return PreparedPlan{}, err
	}
	sortPreparedTransitions(normalized)
	sort.Slice(normalizedPreconditions, func(left, right int) bool {
		return locationLess(
			normalizedPreconditions[left].Target,
			normalizedPreconditions[right].Target,
		)
	})
	return PreparedPlan{
		transitions:      normalized,
		preconditions:    normalizedPreconditions,
		materializations: normalizedMaterializations,
	}, nil
}

func CombinePreparedPlans(plans ...PreparedPlan) (PreparedPlan, error) {
	var transitions []Transition
	var preconditions []ReadPrecondition
	var materializations []SecretMaterializationRecipe
	for _, plan := range plans {
		transitions = append(transitions, plan.Transitions()...)
		preconditions = append(preconditions, plan.Preconditions()...)
		materializations = append(
			materializations,
			plan.Materializations()...,
		)
	}
	return NewPreparedPlanWithMaterializations(
		transitions,
		preconditions,
		materializations,
	)
}

func cloneTransitions(source []Transition) []Transition {
	result := make([]Transition, len(source))
	for index, transition := range source {
		result[index] = Transition{
			ResourceIDs:     append([]string(nil), transition.ResourceIDs...),
			PreparationOnly: transition.PreparationOnly,
			Mutations:       cloneFileMutations(transition.Mutations),
		}
	}
	return result
}

func validatePreparedTransitions(transitions []Transition) error {
	resourceIDs := make(map[string]bool)
	var mutations []FileMutation
	for index := range transitions {
		transition := &transitions[index]
		if len(transition.ResourceIDs) == 0 || len(transition.Mutations) == 0 {
			return fmt.Errorf("prepared configuration transition is empty")
		}
		sort.Strings(transition.ResourceIDs)
		for _, resourceID := range transition.ResourceIDs {
			if !preparedResourceIDPattern.MatchString(resourceID) || resourceIDs[resourceID] {
				return fmt.Errorf("invalid duplicate configuration resource %q", resourceID)
			}
			resourceIDs[resourceID] = true
		}
		sort.Slice(transition.Mutations, func(left, right int) bool {
			return locationLess(
				transition.Mutations[left].Target,
				transition.Mutations[right].Target,
			)
		})
		for _, mutation := range transition.Mutations {
			if err := validatePreparedMutation(mutation); err != nil {
				return err
			}
			for _, previous := range mutations {
				if locationsOverlap(previous.Target, mutation.Target) {
					return fmt.Errorf(
						"configuration targets %v and %v overlap",
						previous.Target,
						mutation.Target,
					)
				}
			}
			mutations = append(mutations, mutation)
		}
	}
	if err := rejectPhysicalAliases(transitions); err != nil {
		return err
	}
	return nil
}

func validateReadPreconditions(
	transitions []Transition,
	preconditions []ReadPrecondition,
) error {
	targets := make(map[domain.Location]bool, len(preconditions))
	for _, precondition := range preconditions {
		if precondition.Kind != ReadPreconditionSymlink {
			return fmt.Errorf("invalid read precondition kind")
		}
		if !precondition.Target.Valid() ||
			!precondition.Target.Path.Portable() {
			return fmt.Errorf(
				"invalid read precondition target %v",
				precondition.Target,
			)
		}
		if precondition.Device == 0 ||
			precondition.Inode == 0 ||
			precondition.BirthSeconds <= 0 ||
			precondition.BirthNanoseconds < 0 ||
			precondition.BirthNanoseconds >= 1_000_000_000 {
			return fmt.Errorf("read precondition identity is incomplete")
		}
		if !filepath.IsAbs(precondition.ExpectedTargetPath) ||
			filepath.Clean(precondition.ExpectedTargetPath) !=
				precondition.ExpectedTargetPath {
			return fmt.Errorf("invalid expected symlink target path")
		}
		if targets[precondition.Target] {
			return fmt.Errorf(
				"duplicate read precondition target %v",
				precondition.Target,
			)
		}
		for _, transition := range transitions {
			for _, mutation := range transition.Mutations {
				if locationsOverlap(precondition.Target, mutation.Target) {
					return fmt.Errorf(
						"read precondition target %v overlaps configuration target %v",
						precondition.Target,
						mutation.Target,
					)
				}
			}
		}
		targets[precondition.Target] = true
	}
	return nil
}

func validatePreparedMutation(mutation FileMutation) error {
	if !mutation.Target.Valid() || !mutation.Target.Path.Portable() {
		return fmt.Errorf("invalid configuration target %v", mutation.Target)
	}
	switch mutation.Disposition {
	case MutationPresent:
		if !mutation.After.Exists {
			return fmt.Errorf("present configuration after-image is absent")
		}
	case MutationRemoveExactDocument:
		if len(mutation.After.Content) != 0 || mutation.After.Mode != 0 ||
			mutation.After.Exists || !mutation.Before.Exists ||
			!IsExactDiagnosticsTarget(mutation.Target) {
			return fmt.Errorf("invalid exact document removal")
		}
	case MutationRemoveManagedSecret:
		if len(mutation.After.Content) != 0 || mutation.After.Mode != 0 ||
			mutation.After.Exists || !mutation.Before.Exists ||
			!IsOpenCodeContext7SecretTarget(mutation.Target) {
			return fmt.Errorf("invalid managed secret removal")
		}
	default:
		return fmt.Errorf("invalid configuration mutation disposition")
	}
	if mutation.After.Exists && (mutation.After.Mode > 0o777 ||
		mutation.After.Mode&0o400 == 0) {
		return fmt.Errorf("invalid existing configuration after-image")
	}
	if !mutation.Before.Exists {
		if mutation.Before != (BeforeImage{}) ||
			mutation.After.Mode != privateConfigurationMode {
			return fmt.Errorf("invalid absent configuration before-image")
		}
		return nil
	}
	if !preparedDigestPattern.MatchString(mutation.Before.SHA256) ||
		mutation.Before.Mode > 0o777 || mutation.Before.Mode&0o400 == 0 ||
		mutation.Before.Device == 0 || mutation.Before.Inode == 0 ||
		mutation.Before.BirthSeconds <= 0 ||
		mutation.Before.BirthNanoseconds < 0 ||
		mutation.Before.BirthNanoseconds >= 1_000_000_000 {
		return fmt.Errorf("invalid existing configuration before-image")
	}
	if !mutation.After.Exists {
		return nil
	}
	if mutation.After.Mode != mutation.Before.Mode&privateConfigurationMode ||
		mutation.After.Mode&0o400 == 0 {
		if !exactDiagnosticsModeUpgrade(mutation) {
			return fmt.Errorf("invalid prepared configuration mode")
		}
	}
	return nil
}

func IsOpenCodeContext7SecretTarget(target domain.Location) bool {
	return target.Root == domain.RootOpenCodeConfig &&
		target.Path == "mainframe/secrets/context7-api-key"
}

func exactDiagnosticsModeUpgrade(mutation FileMutation) bool {
	return IsExactDiagnosticsTarget(mutation.Target) &&
		mutation.After.Mode == privateConfigurationMode
}

func IsExactDiagnosticsTarget(target domain.Location) bool {
	expectedRoots := map[domain.RootID]bool{
		domain.RootClaudeConfig:    true,
		domain.RootCodexConfig:     true,
		domain.RootOpenCodeConfig:  true,
		domain.RootAntigravityData: true,
	}
	return expectedRoots[target.Root] &&
		target.Path == "mainframe/diagnostics.json"
}

func sortPreparedTransitions(transitions []Transition) {
	sort.Slice(transitions, func(left, right int) bool {
		return locationLess(
			transitions[left].Mutations[0].Target,
			transitions[right].Mutations[0].Target,
		)
	})
}
