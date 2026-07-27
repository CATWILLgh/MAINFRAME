package credentialcatalog

import (
	"fmt"
	"regexp"
	"sort"
)

var secretNamePattern = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)

type bindingKey struct {
	instance InstanceID
	role     RoleID
}

type requirementKey struct {
	action RequirementAction
	target bindingKey
}

func validateInstances(
	instances []Instance,
	definitions Definitions,
) error {
	ids := make([]string, len(instances))
	bindings := make(map[bindingKey]CredentialBinding)
	for index, instance := range instances {
		ids[index] = string(instance.ID)
		if err := validateInstance(instance, definitions, bindings); err != nil {
			return fmt.Errorf("instance %q: %w", instance.ID, err)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("credential instances must be sorted with unique ids")
	}
	if err := validateRequirements(instances, bindings); err != nil {
		return err
	}
	return rejectRequirementCycles(instances)
}

func validateInstance(
	instance Instance,
	definitions Definitions,
	bindings map[bindingKey]CredentialBinding,
) error {
	service, exists := definitions.Service(instance.ServiceID)
	if !exists {
		return fmt.Errorf("unknown service %q", instance.ServiceID)
	}
	if !validIdentifier(string(instance.ID)) ||
		!validText(instance.Name, 80) ||
		!validText(instance.Purpose, 240) ||
		(instance.Locator != "" && !validText(instance.Locator, 512)) {
		return fmt.Errorf("invalid identity or description")
	}
	if len(instance.Credentials) == 0 {
		return fmt.Errorf("instance must bind a credential")
	}
	roleIDs := roleSet(service)
	ids := make([]string, len(instance.Credentials))
	for index, credential := range instance.Credentials {
		ids[index] = string(credential.RoleID)
		if !roleIDs[credential.RoleID] {
			return fmt.Errorf("unknown role %q", credential.RoleID)
		}
		if err := ValidateSecretReference(credential.Secret); err != nil {
			return fmt.Errorf("role %q: %w", credential.RoleID, err)
		}
		bindings[bindingKey{instance: instance.ID, role: credential.RoleID}] = credential
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("credential bindings must be sorted with unique roles")
	}
	return nil
}

func roleSet(service ServiceDefinition) map[RoleID]bool {
	result := make(map[RoleID]bool, len(service.CredentialRoles))
	for _, role := range service.CredentialRoles {
		result[role.ID] = true
	}
	return result
}

func ValidateSecretReference(reference SecretReference) error {
	if reference.Backend != BackendSecretEnvironment ||
		!secretNamePattern.MatchString(reference.Name) {
		return fmt.Errorf("invalid secret reference")
	}
	return nil
}

func validateRequirements(
	instances []Instance,
	bindings map[bindingKey]CredentialBinding,
) error {
	for _, instance := range instances {
		for _, credential := range instance.Credentials {
			source := bindingKey{instance: instance.ID, role: credential.RoleID}
			seen := make(map[requirementKey]bool)
			for _, requirement := range credential.Requirements {
				key := requirementKey{
					action: requirement.Action,
					target: bindingKey{
						instance: requirement.InstanceID,
						role:     requirement.RoleID,
					},
				}
				if seen[key] {
					return fmt.Errorf(
						"instance %q role %q: duplicate requirement",
						instance.ID,
						credential.RoleID,
					)
				}
				seen[key] = true
				if err := validateRequirement(source, requirement, bindings); err != nil {
					return fmt.Errorf(
						"instance %q role %q: %w",
						instance.ID,
						credential.RoleID,
						err,
					)
				}
			}
		}
	}
	return nil
}

func validateRequirement(
	source bindingKey,
	requirement Requirement,
	bindings map[bindingKey]CredentialBinding,
) error {
	if !validRequirementAction(requirement.Action) ||
		!validText(requirement.Summary, 240) {
		return fmt.Errorf("invalid requirement")
	}
	target := bindingKey{
		instance: requirement.InstanceID,
		role:     requirement.RoleID,
	}
	if target == source {
		return fmt.Errorf("credential cannot require itself")
	}
	if _, exists := bindings[target]; !exists {
		return fmt.Errorf(
			"requirement target %q role %q does not exist",
			requirement.InstanceID,
			requirement.RoleID,
		)
	}
	return nil
}

func validRequirementAction(action RequirementAction) bool {
	switch action {
	case ActionUse, ActionObtain, ActionRotate, ActionRecover:
		return true
	default:
		return false
	}
}

func rejectRequirementCycles(instances []Instance) error {
	edges := requirementEdges(instances)
	visiting := make(map[bindingKey]bool)
	visited := make(map[bindingKey]bool)
	var visit func(bindingKey) bool
	visit = func(node bindingKey) bool {
		if visiting[node] {
			return true
		}
		if visited[node] {
			return false
		}
		visiting[node] = true
		for _, target := range edges[node] {
			if visit(target) {
				return true
			}
		}
		visiting[node] = false
		visited[node] = true
		return false
	}
	for node := range edges {
		if visit(node) {
			return fmt.Errorf("credential requirement graph contains a cycle")
		}
	}
	return nil
}

func requirementEdges(instances []Instance) map[bindingKey][]bindingKey {
	result := make(map[bindingKey][]bindingKey)
	for _, instance := range instances {
		for _, credential := range instance.Credentials {
			source := bindingKey{instance: instance.ID, role: credential.RoleID}
			for _, requirement := range credential.Requirements {
				result[source] = append(result[source], bindingKey{
					instance: requirement.InstanceID,
					role:     requirement.RoleID,
				})
			}
			sort.Slice(result[source], func(left, right int) bool {
				return result[source][left].instance < result[source][right].instance ||
					result[source][left].instance == result[source][right].instance &&
						result[source][left].role < result[source][right].role
			})
		}
	}
	return result
}
