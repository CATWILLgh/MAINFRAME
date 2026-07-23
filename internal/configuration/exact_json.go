package configuration

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ExactJSONDocument struct {
	ResourceID string
	Document   []byte
}

type exactJSONState struct {
	resource releasecontract.Resource
	snapshot fileSnapshot
	after    []byte
	changed  bool
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
			kind := ChangeUpdate
			if !state.snapshot.present {
				kind = ChangeAdd
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
				Target: state.resource.Target,
				Before: beforeImage(state.snapshot),
				After:  append([]byte(nil), state.after...),
				Mode:   privateConfigurationMode,
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
		after, err := exactJSONAfter(item.ResourceID, canonical)
		if err != nil {
			return nil, err
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
		changed := !snapshot.present ||
			snapshot.mode != privateConfigurationMode
		if snapshot.present {
			current, parseErr := jsondocument.Parse(snapshot.raw)
			changed = changed ||
				parseErr != nil ||
				current.Canonical() != canonical
		}
		states = append(states, exactJSONState{
			resource: resource, snapshot: snapshot,
			after: after, changed: changed,
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
	if !exists || seen[item.ResourceID] || len(item.Document) == 0 {
		return releasecontract.Resource{}, "", fmt.Errorf(
			"invalid exact JSON desired resource %q",
			item.ResourceID,
		)
	}
	seen[item.ResourceID] = true
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
