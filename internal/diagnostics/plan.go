package diagnostics

import (
	"errors"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

var canonicalAdapters = []domain.ComponentID{
	domain.ComponentClaudeCode,
	domain.ComponentCodex,
	domain.ComponentOpenCode,
	domain.ComponentAntigravity2,
}

type Desired struct {
	Configured bool
	Events     bool
	Feedback   bool
}

type Intent struct {
	ComponentID domain.ComponentID
	Events      bool
	Feedback    bool
}

type Plan struct {
	Intents    []Intent
	Executable bool
}

func Build(selected []domain.ComponentID, desired Desired) (Plan, error) {
	return BuildLifecycle(selected, nil, desired)
}

func BuildLifecycle(
	selected []domain.ComponentID,
	remove []domain.ComponentID,
	desired Desired,
) (Plan, error) {
	if !desired.Configured {
		if desired.Events || desired.Feedback {
			return Plan{}, errors.New("diagnostics features require diagnostics to be configured")
		}
	}
	if desired.Feedback && !desired.Events {
		return Plan{}, errors.New("harness feedback requires DEV mode")
	}
	selectedSet := make(map[domain.ComponentID]bool, len(selected))
	for _, componentID := range selected {
		selectedSet[componentID] = true
	}
	removeSet := make(map[domain.ComponentID]bool, len(remove))
	for _, componentID := range remove {
		if !selectedSet[componentID] {
			removeSet[componentID] = true
		}
	}
	intents := make([]Intent, 0, len(canonicalAdapters))
	for _, componentID := range canonicalAdapters {
		if desired.Configured && selectedSet[componentID] {
			intents = append(intents, Intent{
				ComponentID: componentID,
				Events:      desired.Events,
				Feedback:    desired.Feedback,
			})
			continue
		}
		if removeSet[componentID] {
			intents = append(intents, Intent{ComponentID: componentID})
		}
	}
	if desired.Configured && len(intents) == 0 {
		return Plan{}, errors.New("configured diagnostics require at least one supported environment")
	}
	return Plan{Intents: intents}, nil
}
