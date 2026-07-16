package configuration

import (
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func (builder *preparationBuilder) applyOwnedMap(
	resource releasecontract.Resource,
	state ownedMapSnapshot,
	selected bool,
) error {
	desired := `{}`
	if selected {
		desired = resource.JSONMapOwnership.DesiredMap
	}
	reconciliation, err := reconcileOwnedJSONMaps(
		state.existingRaw,
		desired,
		state.ownedRaw,
	)
	if err != nil {
		return err
	}
	if !state.configPresent ||
		!orderedDecisionMapsEqual(state.existingRaw, reconciliation.mergedRaw) {
		if err := builder.set(
			resource.Target,
			resource.JSONMapOwnership.MapPointer,
			reconciliation.mergedRaw,
		); err != nil {
			return fmt.Errorf("materialize configuration: %w", err)
		}
	}
	if !state.registryPresent ||
		!ownershipMapsEqual(state.ownedRaw, reconciliation.nextOwnedRaw) {
		if err := builder.prepareRegistry(resource); err != nil {
			return err
		}
		if err := builder.set(
			resource.JSONMapOwnership.RegistryTarget,
			resource.JSONMapOwnership.EntriesPointer,
			reconciliation.nextOwnedRaw,
		); err != nil {
			return fmt.Errorf("materialize ownership registry: %w", err)
		}
	}
	builder.addGroupResource(resource)
	return nil
}

func (builder *preparationBuilder) prepareRegistry(
	resource releasecontract.Resource,
) error {
	target := resource.JSONMapOwnership.RegistryTarget
	snapshot, exists := builder.files[target]
	if !exists {
		return fmt.Errorf("ownership registry snapshot is unavailable")
	}
	if snapshot.present {
		return nil
	}
	return builder.set(
		target,
		"/version",
		fmt.Sprintf("%d", resource.JSONMapOwnership.RegistrySchemaVersion),
	)
}

func (builder *preparationBuilder) addGroupResource(
	resource releasecontract.Resource,
) {
	group := builder.groups[resource.Target]
	if group == nil {
		group = make(map[string]bool)
		builder.groups[resource.Target] = group
	}
	group[resource.ID] = true
	builder.groupByTarget[resource.JSONMapOwnership.RegistryTarget] = resource.Target
}

func orderedDecisionMapsEqual(left, right string) bool {
	leftValue, leftErr := decodeDecisionValue(left)
	rightValue, rightErr := decodeDecisionValue(right)
	if leftErr != nil || rightErr != nil || !reflect.DeepEqual(leftValue, rightValue) {
		return false
	}
	leftKeys, leftErr := topLevelObjectKeys(left)
	rightKeys, rightErr := topLevelObjectKeys(right)
	if leftErr != nil || rightErr != nil || !reflect.DeepEqual(leftKeys, rightKeys) {
		return false
	}
	leftOrder, leftErr := orderedRuleMap(left)
	rightOrder, rightErr := orderedRuleMap(right)
	return leftErr == nil && rightErr == nil &&
		reflect.DeepEqual(leftOrder, rightOrder)
}

func ownershipMapsEqual(left, right string) bool {
	leftValue, leftErr := decodeDecisionMap(left, true)
	rightValue, rightErr := decodeDecisionMap(right, true)
	if leftErr != nil || rightErr != nil || !reflect.DeepEqual(leftValue, rightValue) {
		return false
	}
	leftOrder, leftErr := orderedRuleMap(left)
	rightOrder, rightErr := orderedRuleMap(right)
	return leftErr == nil && rightErr == nil &&
		reflect.DeepEqual(leftOrder, rightOrder)
}
