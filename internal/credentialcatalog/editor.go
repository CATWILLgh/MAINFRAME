package credentialcatalog

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
)

type ChangeKind string

const (
	ChangeCreate ChangeKind = "create"
	ChangeUpdate ChangeKind = "update"
	ChangeDelete ChangeKind = "delete"
)

type InstanceChange struct {
	Kind   ChangeKind
	Before Instance
	After  Instance
}

func BuildInstances(
	values []Instance,
	definitions Definitions,
) (Instances, error) {
	normalized := cloneInstances(values)
	sort.Slice(normalized, func(left, right int) bool {
		return normalized[left].ID < normalized[right].ID
	})
	for index := range normalized {
		sort.Slice(normalized[index].Credentials, func(left, right int) bool {
			return normalized[index].Credentials[left].RoleID <
				normalized[index].Credentials[right].RoleID
		})
		for bindingIndex := range normalized[index].Credentials {
			requirements := normalized[index].Credentials[bindingIndex].Requirements
			sort.Slice(requirements, func(left, right int) bool {
				if requirements[left].Action != requirements[right].Action {
					return requirements[left].Action < requirements[right].Action
				}
				if requirements[left].InstanceID != requirements[right].InstanceID {
					return requirements[left].InstanceID <
						requirements[right].InstanceID
				}
				return requirements[left].RoleID < requirements[right].RoleID
			})
		}
	}
	if err := validateInstances(normalized, definitions); err != nil {
		return Instances{}, err
	}
	return Instances{instances: normalized}, nil
}

func CreateInstance(
	current Instances,
	instance Instance,
	definitions Definitions,
) (Instances, InstanceChange, error) {
	for _, existing := range current.instances {
		if existing.ID == instance.ID {
			return Instances{}, InstanceChange{}, fmt.Errorf(
				"credential instance %q already exists",
				instance.ID,
			)
		}
	}
	updated, err := BuildInstances(
		append(current.All(), cloneInstance(instance)),
		definitions,
	)
	if err != nil {
		return Instances{}, InstanceChange{}, err
	}
	return updated, InstanceChange{
		Kind:  ChangeCreate,
		After: cloneInstance(instance),
	}, nil
}

func EditInstance(
	current Instances,
	id InstanceID,
	replacement Instance,
	definitions Definitions,
) (Instances, InstanceChange, error) {
	values := current.All()
	for index, existing := range values {
		if existing.ID != id {
			continue
		}
		if replacement.ID != existing.ID {
			return Instances{}, InstanceChange{}, fmt.Errorf(
				"credential instance identity cannot change",
			)
		}
		if replacement.ServiceID != existing.ServiceID {
			return Instances{}, InstanceChange{}, fmt.Errorf(
				"credential instance service cannot change",
			)
		}
		values[index] = cloneInstance(replacement)
		updated, err := BuildInstances(values, definitions)
		if err != nil {
			return Instances{}, InstanceChange{}, err
		}
		return updated, InstanceChange{
			Kind: ChangeUpdate, Before: existing,
			After: cloneInstance(replacement),
		}, nil
	}
	return Instances{}, InstanceChange{}, fmt.Errorf(
		"credential instance %q does not exist",
		id,
	)
}

func DeleteInstance(
	current Instances,
	id InstanceID,
	definitions Definitions,
) (Instances, InstanceChange, error) {
	values := current.All()
	for index, existing := range values {
		if existing.ID != id {
			continue
		}
		desired, err := BuildInstances(
			append(values[:index:index], values[index+1:]...),
			definitions,
		)
		if err != nil {
			return Instances{}, InstanceChange{}, err
		}
		return desired, InstanceChange{
			Kind:   ChangeDelete,
			Before: cloneInstance(existing),
		}, nil
	}
	return Instances{}, InstanceChange{}, fmt.Errorf(
		"credential instance %q does not exist",
		id,
	)
}

func EncodeInstances(instances Instances) ([]byte, error) {
	document := instancesDocument{
		SchemaVersion: schemaVersion,
		Kind:          instancesKind,
		Instances:     instances.All(),
	}
	var output bytes.Buffer
	encoder := json.NewEncoder(&output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(document); err != nil {
		return nil, fmt.Errorf("encode credential instances: %w", err)
	}
	return output.Bytes(), nil
}

func PlanInstanceChanges(
	current Instances,
	desired Instances,
) ([]InstanceChange, error) {
	currentByID := make(map[InstanceID]Instance, len(current.instances))
	for _, instance := range current.instances {
		currentByID[instance.ID] = instance
	}
	changes := make([]InstanceChange, 0)
	for _, instance := range desired.instances {
		before, exists := currentByID[instance.ID]
		if !exists {
			changes = append(changes, InstanceChange{
				Kind:  ChangeCreate,
				After: cloneInstance(instance),
			})
			continue
		}
		delete(currentByID, instance.ID)
		if before.ServiceID != instance.ServiceID {
			return nil, fmt.Errorf(
				"credential instance %q changed service",
				instance.ID,
			)
		}
		if !instancesEqual(before, instance) {
			changes = append(changes, InstanceChange{
				Kind: ChangeUpdate, Before: cloneInstance(before),
				After: cloneInstance(instance),
			})
		}
	}
	for _, instance := range current.instances {
		if _, exists := currentByID[instance.ID]; !exists {
			continue
		}
		changes = append(changes, InstanceChange{
			Kind:   ChangeDelete,
			Before: cloneInstance(instance),
		})
	}
	return changes, nil
}

func instancesEqual(left, right Instance) bool {
	leftPayload, leftErr := json.Marshal(left)
	rightPayload, rightErr := json.Marshal(right)
	return leftErr == nil && rightErr == nil &&
		bytes.Equal(leftPayload, rightPayload)
}
