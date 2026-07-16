package configuration

import (
	"fmt"
	"reflect"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ChangeKind string

const (
	ChangeAdd        ChangeKind = "add"
	ChangeUpdate     ChangeKind = "update"
	ChangeRemove     ChangeKind = "remove"
	ChangeRelinquish ChangeKind = "relinquish"
)

type IssueKind string

const (
	IssueAttention           IssueKind = "attention"
	IssueNotAssessed         IssueKind = "not_assessed"
	IssueRemovalUnsupported  IssueKind = "removal_unsupported"
	IssuePlanningUnavailable IssueKind = "planning_unavailable"
)

type Change struct {
	ResourceID  string
	ComponentID domain.ComponentID
	UnitID      string
	Kind        ChangeKind
}

type Issue struct {
	ResourceID  string
	ComponentID domain.ComponentID
	UnitID      string
	Kind        IssueKind
	Reason      Reason
}

type Plan struct {
	Changes []Change
	Issues  []Issue
}

func (inspection Inspection) Plan(included []domain.ComponentID) (Plan, error) {
	if err := Validate(inspection.resources, inspection.observations); err != nil {
		return Plan{}, fmt.Errorf("invalid configuration inspection: %w", err)
	}
	selected := make(map[domain.ComponentID]bool, len(included))
	for _, component := range included {
		selected[component] = true
	}
	observations := make(map[string]Observation, len(inspection.observations))
	for _, observation := range inspection.observations {
		observations[observation.ResourceID] = observation
	}
	var plan Plan
	for _, resource := range inspection.resources {
		observation := observations[resource.ID]
		if resource.JSONMapOwnership != nil {
			planOwnedMap(&plan, resource, observation, inspection.ownedMaps, selected)
		} else {
			planGeneric(&plan, resource, observation, selected[resource.ComponentID])
		}
	}
	sortPlan(&plan)
	return plan, nil
}

func planGeneric(
	plan *Plan,
	resource releasecontract.Resource,
	observation Observation,
	selected bool,
) {
	if observation.Status == Attention || observation.Status == NotAssessed {
		plan.Issues = append(plan.Issues, issueForObservation(resource, observation))
		return
	}
	if selected {
		if kind, changed := selectedGenericChange(observation); changed {
			plan.Changes = append(plan.Changes, changeForResource(resource, kind, ""))
		}
		return
	}
	if genericRemovalPresent(observation) {
		plan.Issues = append(plan.Issues, Issue{
			ResourceID: resource.ID, ComponentID: resource.ComponentID,
			Kind: IssueRemovalUnsupported, Reason: observation.Reason,
		})
	}
}

func selectedGenericChange(observation Observation) (ChangeKind, bool) {
	switch observation.Reason {
	case ResourceMissing, DirectoryMissing, LineMissing:
		return ChangeAdd, true
	case JSONFieldsDrifted:
		return ChangeUpdate, true
	default:
		return "", false
	}
}

func genericRemovalPresent(observation Observation) bool {
	switch observation.Reason {
	case ResourceExists, DirectoryExists, LinePresent, JSONFieldsMatch,
		JSONFieldsDrifted:
		return true
	default:
		return false
	}
}

func planOwnedMap(
	plan *Plan,
	resource releasecontract.Resource,
	observation Observation,
	states map[string]ownedMapSnapshot,
	selected map[domain.ComponentID]bool,
) {
	if observation.Status == Attention || observation.Status == NotAssessed {
		plan.Issues = append(plan.Issues, issueForObservation(resource, observation))
		return
	}
	state, exists := states[resource.ID]
	if !exists {
		plan.Issues = append(plan.Issues, Issue{
			ResourceID: resource.ID, ComponentID: resource.ComponentID,
			Kind: IssuePlanningUnavailable, Reason: observation.Reason,
		})
		return
	}
	desired := `{}`
	isSelected := selected[resource.ComponentID]
	if isSelected {
		desired = resource.JSONMapOwnership.DesiredMap
	}
	reconciliation, err := reconcileOwnedJSONMaps(
		state.existingRaw,
		desired,
		state.ownedRaw,
	)
	if err != nil {
		plan.Issues = append(plan.Issues, Issue{
			ResourceID: resource.ID, ComponentID: resource.ComponentID,
			Kind: IssuePlanningUnavailable, Reason: JSONDocumentInvalid,
		})
		return
	}
	start := len(plan.Changes)
	classifyOwnedChanges(plan, resource, state, reconciliation, isSelected)
	if isSelected && len(plan.Changes) == start &&
		(!state.configPresent || !state.registryPresent) {
		plan.Changes = append(
			plan.Changes,
			changeForResource(resource, ChangeAdd, ""),
		)
	}
}

func issueForObservation(
	resource releasecontract.Resource,
	observation Observation,
) Issue {
	kind := IssueAttention
	if observation.Status == NotAssessed {
		kind = IssueNotAssessed
	}
	return Issue{
		ResourceID: resource.ID, ComponentID: resource.ComponentID,
		Kind: kind, Reason: observation.Reason,
	}
}

func changeForResource(
	resource releasecontract.Resource,
	kind ChangeKind,
	unit string,
) Change {
	return Change{
		ResourceID: resource.ID, ComponentID: resource.ComponentID,
		UnitID: unit, Kind: kind,
	}
}

func classifyOwnedChanges(
	plan *Plan,
	resource releasecontract.Resource,
	state ownedMapSnapshot,
	next ownedMapReconciliation,
	selected bool,
) {
	existing, _ := decodeDecisionValue(state.existingRaw)
	owned, _ := decodeDecisionMap(state.ownedRaw, true)
	existingMap, _ := existing.(map[string]any)
	mergedMap, _ := next.merged.(map[string]any)
	actions := ownedActionIDs(existingMap, owned, mergedMap, next.nextOwned)
	for _, action := range actions {
		kind, changed := ownedActionChange(
			action,
			existingMap,
			owned,
			mergedMap,
			state.existingOrder,
			next,
			selected,
		)
		if changed {
			plan.Changes = append(
				plan.Changes,
				changeForResource(resource, kind, action),
			)
		}
	}
}

func ownedActionChange(
	action string,
	existing, owned, merged map[string]any,
	existingOrder map[string]string,
	next ownedMapReconciliation,
	selected bool,
) (ChangeKind, bool) {
	actual, actualExists := existing[action]
	previous, tracked := owned[action]
	result, resultExists := merged[action]
	nextValue, nextTracked := next.nextOwned[action]
	wasActive := tracked && previous != nil
	isActive := nextTracked && nextValue != nil
	switch {
	case wasActive && !isActive && actualExists && !resultExists:
		return ChangeRemove, true
	case wasActive && !isActive:
		return ChangeRelinquish, true
	case wasActive && isActive && (!reflect.DeepEqual(actual, result) ||
		existingOrder[action] != next.mergedOrder[action]):
		return ChangeUpdate, true
	case !wasActive && isActive && !actualExists:
		return ChangeAdd, true
	case selected && nextTracked && nextValue == nil &&
		(!tracked || previous != nil):
		return ChangeRelinquish, true
	default:
		return "", false
	}
}

func ownedActionIDs(maps ...map[string]any) []string {
	seen := make(map[string]bool)
	for _, values := range maps {
		for action := range values {
			seen[action] = true
		}
	}
	result := make([]string, 0, len(seen))
	for action := range seen {
		result = append(result, action)
	}
	sort.Strings(result)
	return result
}

func sortPlan(plan *Plan) {
	sort.Slice(plan.Changes, func(left, right int) bool {
		a, b := plan.Changes[left], plan.Changes[right]
		if a.ResourceID != b.ResourceID {
			return a.ResourceID < b.ResourceID
		}
		if a.UnitID != b.UnitID {
			return a.UnitID < b.UnitID
		}
		return a.Kind < b.Kind
	})
	sort.Slice(plan.Issues, func(left, right int) bool {
		a, b := plan.Issues[left], plan.Issues[right]
		if a.ResourceID != b.ResourceID {
			return a.ResourceID < b.ResourceID
		}
		if a.UnitID != b.UnitID {
			return a.UnitID < b.UnitID
		}
		return a.Kind < b.Kind
	})
}
