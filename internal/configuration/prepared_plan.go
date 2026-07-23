package configuration

import (
	"fmt"
	"regexp"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

var preparedResourceIDPattern = regexp.MustCompile(
	`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`,
)

var preparedDigestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

func NewPreparedPlan(transitions []Transition) (PreparedPlan, error) {
	normalized := cloneTransitions(transitions)
	if err := validatePreparedTransitions(normalized); err != nil {
		return PreparedPlan{}, err
	}
	sortPreparedTransitions(normalized)
	return PreparedPlan{transitions: normalized}, nil
}

func CombinePreparedPlans(plans ...PreparedPlan) (PreparedPlan, error) {
	var transitions []Transition
	for _, plan := range plans {
		transitions = append(transitions, plan.Transitions()...)
	}
	return NewPreparedPlan(transitions)
}

func cloneTransitions(source []Transition) []Transition {
	result := make([]Transition, len(source))
	for index, transition := range source {
		result[index] = Transition{
			ResourceIDs: append([]string(nil), transition.ResourceIDs...),
			Mutations:   cloneFileMutations(transition.Mutations),
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

func validatePreparedMutation(mutation FileMutation) error {
	if !mutation.Target.Valid() || !mutation.Target.Path.Portable() {
		return fmt.Errorf("invalid configuration target %v", mutation.Target)
	}
	if !mutation.Before.Exists {
		if mutation.Before != (BeforeImage{}) || mutation.Mode != privateConfigurationMode {
			return fmt.Errorf("invalid absent configuration before-image")
		}
		return nil
	}
	if !preparedDigestPattern.MatchString(mutation.Before.SHA256) ||
		mutation.Before.Mode > 0o777 || mutation.Before.Mode&0o400 == 0 ||
		mutation.Before.Device == 0 || mutation.Before.Inode == 0 {
		return fmt.Errorf("invalid existing configuration before-image")
	}
	if mutation.Mode != mutation.Before.Mode&privateConfigurationMode ||
		mutation.Mode&0o400 == 0 {
		if !exactDiagnosticsModeUpgrade(mutation) {
			return fmt.Errorf("invalid prepared configuration mode")
		}
	}
	return nil
}

func exactDiagnosticsModeUpgrade(mutation FileMutation) bool {
	expectedRoots := map[domain.RootID]bool{
		domain.RootClaudeConfig:      true,
		domain.RootCodexConfig:       true,
		domain.RootOpenCodeConfig:    true,
		domain.RootAntigravityConfig: true,
	}
	return expectedRoots[mutation.Target.Root] &&
		mutation.Target.Path == "mainframe/diagnostics.json" &&
		mutation.Mode == privateConfigurationMode
}

func sortPreparedTransitions(transitions []Transition) {
	sort.Slice(transitions, func(left, right int) bool {
		return locationLess(
			transitions[left].Mutations[0].Target,
			transitions[right].Mutations[0].Target,
		)
	})
}
