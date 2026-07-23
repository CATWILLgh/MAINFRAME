package mcpconfiguration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func findPreparedAfter(
	t *testing.T,
	transitions []configuration.Transition,
	target domain.Location,
) []byte {
	t.Helper()
	return findPreparedMutation(t, transitions, target).After.Content
}

func findPreparedMutation(
	t *testing.T,
	transitions []configuration.Transition,
	target domain.Location,
) *configuration.FileMutation {
	t.Helper()
	for transitionIndex := range transitions {
		for mutationIndex := range transitions[transitionIndex].Mutations {
			mutation := &transitions[transitionIndex].Mutations[mutationIndex]
			if mutation.Target == target {
				return mutation
			}
		}
	}
	t.Fatalf("mutation for %v is absent: %#v", target, transitions)
	return nil
}
