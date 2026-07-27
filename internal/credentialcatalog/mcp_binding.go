package credentialcatalog

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func (snapshot InstanceSnapshot) ResolveMCPSecret(
	instances Instances,
	serverID mcpcatalog.ServerID,
	profileID mcpcatalog.ProfileID,
	instanceID InstanceID,
) (SecretReference, error) {
	if err := validateInstances(instances.All(), snapshot.definitions); err != nil {
		return SecretReference{}, fmt.Errorf(
			"validate effective credential instances: %w",
			err,
		)
	}
	service, err := snapshot.mcpCredentialService(serverID, profileID)
	if err != nil {
		return SecretReference{}, err
	}
	instance, exists := instanceByID(instances, instanceID)
	if !exists || instance.ServiceID != service.ID {
		return SecretReference{}, fmt.Errorf(
			"credential instance %q does not belong to the selected MCP profile",
			instanceID,
		)
	}
	if len(service.CredentialRoles) != 1 {
		return SecretReference{}, fmt.Errorf(
			"MCP credential service %q has an ambiguous role contract",
			service.ID,
		)
	}
	roleID := service.CredentialRoles[0].ID
	for _, binding := range instance.Credentials {
		if binding.RoleID == roleID {
			return binding.Secret, nil
		}
	}
	return SecretReference{}, fmt.Errorf(
		"credential instance %q does not bind role %q",
		instanceID,
		roleID,
	)
}

func (snapshot InstanceSnapshot) mcpCredentialService(
	serverID mcpcatalog.ServerID,
	profileID mcpcatalog.ProfileID,
) (ServiceDefinition, error) {
	var matched *ServiceDefinition
	for _, service := range snapshot.definitions.Services() {
		source := service.Source
		if source.Kind != SourceMCPProfile ||
			source.ServerID != string(serverID) ||
			source.ProfileID != string(profileID) ||
			source.CredentialKind != CredentialAPIKey {
			continue
		}
		if matched != nil {
			return ServiceDefinition{}, fmt.Errorf(
				"MCP profile has multiple credential services",
			)
		}
		copy := service
		matched = &copy
	}
	if matched == nil {
		return ServiceDefinition{}, fmt.Errorf(
			"MCP profile %q has no credential service",
			profileID,
		)
	}
	return *matched, nil
}

func instanceByID(
	instances Instances,
	instanceID InstanceID,
) (Instance, bool) {
	for _, instance := range instances.All() {
		if instance.ID == instanceID {
			return instance, true
		}
	}
	return Instance{}, false
}
