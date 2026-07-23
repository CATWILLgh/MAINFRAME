package configuration

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ExactJSONDocument struct {
	ResourceID  string
	Disposition ExactJSONDisposition
	Document    []byte
}

type ExactJSONDisposition string

const (
	ExactJSONPresent ExactJSONDisposition = "present"
	ExactJSONAbsent  ExactJSONDisposition = "absent"
)

type exactJSONState struct {
	resource    releasecontract.Resource
	snapshot    fileSnapshot
	disposition ExactJSONDisposition
	after       []byte
	changed     bool
}

func (inspection Inspection) PlanExactJSONDocuments(
	desired []ExactJSONDocument,
) (Plan, error) {
	states, err := inspection.exactJSONStates(desired)
	if err != nil {
		return Plan{}, err
	}
	var plan Plan
	for _, state := range states {
		observation := inspection.observationFor(state.resource.ID)
		if observation.Status == Attention ||
			observation.Status == NotAssessed {
			plan.Issues = append(
				plan.Issues,
				issueForObservation(state.resource, observation),
			)
			continue
		}
		if state.changed {
			kind := ChangeRemove
			if state.disposition == ExactJSONPresent && !state.snapshot.present {
				kind = ChangeAdd
			} else if state.disposition == ExactJSONPresent {
				kind = ChangeUpdate
			}
			plan.Changes = append(
				plan.Changes,
				changeForResource(state.resource, kind, ""),
			)
		}
	}
	sortPlan(&plan)
	return plan, nil
}

func (inspection Inspection) PrepareExactJSONDocuments(
	desired []ExactJSONDocument,
) (PreparedPlan, error) {
	states, err := inspection.exactJSONStates(desired)
	if err != nil {
		return PreparedPlan{}, err
	}
	plan, err := inspection.PlanExactJSONDocuments(desired)
	if err != nil {
		return PreparedPlan{}, err
	}
	if len(plan.Issues) != 0 {
		return PreparedPlan{}, fmt.Errorf(
			"exact JSON plan has %d unresolved issue(s)",
			len(plan.Issues),
		)
	}
	transitions := make([]Transition, 0, len(states))
	for _, state := range states {
		if !state.changed {
			continue
		}
		transitions = append(transitions, Transition{
			ResourceIDs: []string{state.resource.ID},
			Mutations: []FileMutation{{
				Disposition: mutationDispositionForExactJSON(
					state.disposition,
				),
				Target: state.resource.Target,
				Before: beforeImage(state.snapshot),
				After: afterImageForExactJSON(
					state.disposition,
					state.after,
				),
			}},
		})
	}
	return NewPreparedPlan(transitions)
}

func (inspection Inspection) exactJSONStates(
	desired []ExactJSONDocument,
) ([]exactJSONState, error) {
	resources := make(map[string]releasecontract.Resource)
	for _, resource := range inspection.resources {
		if resource.Strategy == releasecontract.StrategyExactJSONDocument {
			resources[resource.ID] = resource
		}
	}
	seen := make(map[string]bool, len(desired))
	states := make([]exactJSONState, 0, len(desired))
	for _, item := range desired {
		resource, canonical, err := exactJSONDesired(item, resources, seen)
		if err != nil {
			return nil, err
		}
		var after []byte
		if item.Disposition == ExactJSONPresent {
			after, err = exactJSONAfter(item.ResourceID, canonical)
			if err != nil {
				return nil, err
			}
		}
		snapshot, exists := inspection.files[resource.Target]
		if !exists {
			observation := inspection.observationFor(resource.ID)
			if observation.Status != Attention &&
				observation.Status != NotAssessed {
				return nil, fmt.Errorf(
					"exact JSON snapshot %q is unavailable",
					item.ResourceID,
				)
			}
		}
		changed := snapshot.present
		if item.Disposition == ExactJSONPresent {
			changed = !snapshot.present ||
				snapshot.mode != privateConfigurationMode
		}
		if item.Disposition == ExactJSONPresent && snapshot.present {
			current, parseErr := jsondocument.Parse(snapshot.raw)
			changed = changed ||
				parseErr != nil ||
				current.Canonical() != canonical
		}
		states = append(states, exactJSONState{
			resource: resource, snapshot: snapshot,
			disposition: item.Disposition,
			after:       after,
			changed:     changed,
		})
	}
	sort.Slice(states, func(left, right int) bool {
		return states[left].resource.ID < states[right].resource.ID
	})
	return states, nil
}

func exactJSONDesired(
	item ExactJSONDocument,
	resources map[string]releasecontract.Resource,
	seen map[string]bool,
) (releasecontract.Resource, string, error) {
	resource, exists := resources[item.ResourceID]
	if !exists || seen[item.ResourceID] {
		return releasecontract.Resource{}, "", fmt.Errorf(
			"invalid exact JSON desired resource %q",
			item.ResourceID,
		)
	}
	seen[item.ResourceID] = true
	switch item.Disposition {
	case ExactJSONAbsent:
		if len(item.Document) != 0 {
			return releasecontract.Resource{}, "", fmt.Errorf(
				"absent exact JSON desired resource %q has document bytes",
				item.ResourceID,
			)
		}
		return resource, "", nil
	case ExactJSONPresent:
		if len(item.Document) == 0 {
			return releasecontract.Resource{}, "", fmt.Errorf(
				"present exact JSON desired resource %q has no document bytes",
				item.ResourceID,
			)
		}
	default:
		return releasecontract.Resource{}, "", fmt.Errorf(
			"invalid exact JSON disposition for resource %q",
			item.ResourceID,
		)
	}
	canonical, err := resource.ValidateExactJSONDocument(item.Document)
	if err != nil {
		return releasecontract.Resource{}, "", fmt.Errorf(
			"validate exact JSON desired resource %q: %w",
			item.ResourceID,
			err,
		)
	}
	return resource, canonical, nil
}

func mutationDispositionForExactJSON(
	disposition ExactJSONDisposition,
) MutationDisposition {
	if disposition == ExactJSONAbsent {
		return MutationRemoveExactDocument
	}
	return MutationPresent
}

func afterImageForExactJSON(
	disposition ExactJSONDisposition,
	content []byte,
) AfterImage {
	if disposition == ExactJSONAbsent {
		return AfterImage{}
	}
	return AfterImage{
		Exists:  true,
		Content: append([]byte(nil), content...),
		Mode:    privateConfigurationMode,
	}
}

func exactJSONAfter(resourceID string, canonical string) ([]byte, error) {
	document, err := jsondocument.Parse([]byte(canonical))
	if err != nil {
		return nil, fmt.Errorf(
			"parse canonical exact JSON resource %q: %w",
			resourceID,
			err,
		)
	}
	return document.Indented(), nil
}

func (inspection Inspection) observationFor(resourceID string) Observation {
	for _, observation := range inspection.observations {
		if observation.ResourceID == resourceID {
			return observation
		}
	}
	return Observation{}
}
