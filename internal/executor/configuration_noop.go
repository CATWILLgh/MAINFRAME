package executor

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
)

func (executor Executor) collapseConfigurationNoOps(
	plan configuration.PreparedPlan,
) (configuration.PreparedPlan, error) {
	transitions := plan.Transitions()
	if len(transitions) == 0 {
		return plan, nil
	}
	if executor.configurations == nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"configuration workspace is required",
		)
	}
	result := make([]configuration.Transition, 0, len(transitions))
	for _, transition := range transitions {
		retained, err := executor.retainChangedConfigurations(transition)
		if err != nil {
			return configuration.PreparedPlan{}, err
		}
		if len(retained.Mutations) > 0 {
			result = append(result, retained)
		}
	}
	return configuration.NewPreparedPlanWithPreconditions(
		result,
		plan.Preconditions(),
	)
}

func (executor Executor) retainChangedConfigurations(
	transition configuration.Transition,
) (configuration.Transition, error) {
	retained := configuration.Transition{
		ResourceIDs:     append([]string(nil), transition.ResourceIDs...),
		PreparationOnly: transition.PreparationOnly,
		Mutations: make(
			[]configuration.FileMutation,
			0,
			len(transition.Mutations),
		),
	}
	for _, mutation := range transition.Mutations {
		state, err := executor.configurations.InspectConfiguration(
			mutation.Target,
		)
		if errors.Is(err, fs.ErrNotExist) {
			retained.Mutations = append(retained.Mutations, mutation)
			continue
		}
		if err != nil {
			return configuration.Transition{}, fmt.Errorf(
				"inspect configuration %v before journal: %w",
				mutation.Target,
				err,
			)
		}
		if !verifiedConfigurationNoOp(state, mutation.After) {
			retained.Mutations = append(retained.Mutations, mutation)
		}
	}
	return retained, nil
}

func verifiedConfigurationNoOp(
	state ConfigurationState,
	desired configuration.AfterImage,
) bool {
	if !desired.Exists || !state.Exists {
		return false
	}
	return state.SHA256 == payloadDigestForAfter(desired.Content) &&
		state.Mode == desired.Mode &&
		validFileIdentity(state.Parent) &&
		validFileIdentity(state.Entry)
}

func payloadDigestForAfter(payload []byte) string {
	return fmt.Sprintf("%x", sha256.Sum256(payload))
}
