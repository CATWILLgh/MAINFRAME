package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
)

const credentialsResponseSchemaVersion = 1

var (
	errCredentialDefinitions = errors.New(
		"bundled credential definitions are incompatible with this release",
	)
	errCredentialLocation = errors.New(
		"credential metadata location is unavailable",
	)
	errCredentialInstancesUnsafe = errors.New(
		"user instance document is unsafe or unreadable",
	)
	errCredentialInstancesInvalid = errors.New(
		"user instance document is invalid",
	)
)

type credentialResponse struct {
	SchemaVersion      int                  `json:"schema_version"`
	Kind               string               `json:"kind"`
	SecretAvailability string               `json:"secret_availability"`
	Services           []credentialService  `json:"services"`
	Instances          []credentialInstance `json:"instances"`
}

type credentialService struct {
	ID              string           `json:"id"`
	Name            string           `json:"name"`
	Summary         string           `json:"summary"`
	Source          credentialSource `json:"source"`
	CredentialRoles []credentialRole `json:"credential_roles"`
}

type credentialSource struct {
	Kind           string `json:"kind"`
	ServerID       string `json:"server_id,omitempty"`
	ProfileID      string `json:"profile_id,omitempty"`
	CredentialKind string `json:"credential_kind,omitempty"`
}

type credentialRole struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Purpose     string `json:"purpose"`
	Acquisition string `json:"acquisition"`
}

type credentialInstance struct {
	ID          string              `json:"id"`
	ServiceID   string              `json:"service_id"`
	Name        string              `json:"name"`
	Purpose     string              `json:"purpose"`
	Locator     string              `json:"locator,omitempty"`
	Credentials []credentialBinding `json:"credentials"`
}

type credentialBinding struct {
	RoleID       string                    `json:"role_id"`
	Secret       credentialSecretReference `json:"secret"`
	Requirements []credentialRequirement   `json:"requirements,omitempty"`
}

type credentialSecretReference struct {
	Backend string `json:"backend"`
	Name    string `json:"name"`
}

type credentialRequirement struct {
	Action     string `json:"action"`
	InstanceID string `json:"instance_id"`
	RoleID     string `json:"role_id"`
	Summary    string `json:"summary"`
}

type credentialUsesResponse struct {
	SchemaVersion int                       `json:"schema_version"`
	Kind          string                    `json:"kind"`
	Scope         string                    `json:"scope"`
	Secret        credentialSecretReference `json:"secret"`
	Uses          []credentialUseResponse   `json:"uses"`
}

type credentialUseResponse struct {
	InstanceID   string `json:"instance_id"`
	ServiceID    string `json:"service_id"`
	InstanceName string `json:"instance_name"`
	RoleID       string `json:"role_id"`
}

func runCredentials(output io.Writer) error {
	definitions, instances, err := loadCredentialCatalog()
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(publicCredentialResponse(
		definitions,
		instances.All(),
	)); err != nil {
		return fmt.Errorf("encode response: %w", err)
	}
	return nil
}

func runCredentialUses(
	reference credentialcatalog.SecretReference,
	output io.Writer,
) error {
	_, instances, err := loadCredentialCatalog()
	if err != nil {
		return err
	}
	response := publicCredentialUses(reference, instances)
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(response); err != nil {
		return fmt.Errorf("encode response: %w", err)
	}
	return nil
}

func loadCredentialCatalog() (
	credentialcatalog.Definitions,
	credentialcatalog.Instances,
	error,
) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return credentialcatalog.Definitions{}, credentialcatalog.Instances{}, err
	}
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		snapshot.release.MCPCatalog,
	)
	if err != nil {
		return credentialcatalog.Definitions{}, credentialcatalog.Instances{},
			errCredentialDefinitions
	}
	instances, err := loadCredentialInstances(snapshot, definitions)
	return definitions, instances, err
}

func loadCredentialInstances(
	snapshot readOnlyReleaseSnapshot,
	definitions credentialcatalog.Definitions,
) (credentialcatalog.Instances, error) {
	layout, err := hostlayout.Resolve(hostEnvironment(), snapshot.root)
	if err != nil {
		return credentialcatalog.Instances{}, errCredentialLocation
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return credentialcatalog.Instances{}, errCredentialLocation
	}
	entry, err := namespace.Inspect(domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: credentialcatalog.UserInstancesPath,
	}, true)
	if errors.Is(err, fs.ErrNotExist) {
		return credentialcatalog.BuildInstances(nil, definitions)
	}
	if err != nil || entry.Kind != hostfs.EntryRegular {
		return credentialcatalog.Instances{}, errCredentialInstancesUnsafe
	}
	instances, err := credentialcatalog.ParseInstances(entry.Content, definitions)
	if err != nil {
		return credentialcatalog.Instances{}, errCredentialInstancesInvalid
	}
	return instances, nil
}

func publicCredentialUses(
	reference credentialcatalog.SecretReference,
	instances credentialcatalog.Instances,
) credentialUsesResponse {
	uses := instances.Uses(reference)
	publicUses := make([]credentialUseResponse, len(uses))
	for index, use := range uses {
		publicUses[index] = credentialUseResponse{
			InstanceID: string(use.InstanceID), ServiceID: string(use.ServiceID),
			InstanceName: use.InstanceName, RoleID: string(use.RoleID),
		}
	}
	return credentialUsesResponse{
		SchemaVersion: credentialsResponseSchemaVersion,
		Kind:          "mainframe-credential-secret-uses",
		Scope:         "credential-instance-references",
		Secret: credentialSecretReference{
			Backend: string(reference.Backend), Name: reference.Name,
		},
		Uses: publicUses,
	}
}

func publicCredentialResponse(
	definitions credentialcatalog.Definitions,
	instances []credentialcatalog.Instance,
) credentialResponse {
	return credentialResponse{
		SchemaVersion:      credentialsResponseSchemaVersion,
		Kind:               "mainframe-credential-catalog",
		SecretAvailability: "unchecked",
		Services:           publicCredentialServices(definitions.Services()),
		Instances:          publicCredentialInstances(instances),
	}
}

func publicCredentialServices(
	services []credentialcatalog.ServiceDefinition,
) []credentialService {
	result := make([]credentialService, len(services))
	for index, service := range services {
		roles := make([]credentialRole, len(service.CredentialRoles))
		for roleIndex, role := range service.CredentialRoles {
			roles[roleIndex] = credentialRole{
				ID: string(role.ID), Name: role.Name,
				Purpose: role.Purpose, Acquisition: role.Acquisition,
			}
		}
		result[index] = credentialService{
			ID: string(service.ID), Name: service.Name, Summary: service.Summary,
			Source: credentialSource{
				Kind: string(service.Source.Kind), ServerID: service.Source.ServerID,
				ProfileID:      service.Source.ProfileID,
				CredentialKind: string(service.Source.CredentialKind),
			},
			CredentialRoles: roles,
		}
	}
	return result
}

func publicCredentialInstances(
	instances []credentialcatalog.Instance,
) []credentialInstance {
	result := make([]credentialInstance, len(instances))
	for index, instance := range instances {
		result[index] = credentialInstance{
			ID: string(instance.ID), ServiceID: string(instance.ServiceID),
			Name: instance.Name, Purpose: instance.Purpose, Locator: instance.Locator,
			Credentials: publicCredentialBindings(instance.Credentials),
		}
	}
	return result
}

func publicCredentialBindings(
	bindings []credentialcatalog.CredentialBinding,
) []credentialBinding {
	result := make([]credentialBinding, len(bindings))
	for index, binding := range bindings {
		requirements := make([]credentialRequirement, len(binding.Requirements))
		for requirementIndex, requirement := range binding.Requirements {
			requirements[requirementIndex] = credentialRequirement{
				Action: string(requirement.Action), InstanceID: string(requirement.InstanceID),
				RoleID: string(requirement.RoleID), Summary: requirement.Summary,
			}
		}
		result[index] = credentialBinding{
			RoleID: string(binding.RoleID),
			Secret: credentialSecretReference{
				Backend: string(binding.Secret.Backend), Name: binding.Secret.Name,
			},
			Requirements: requirements,
		}
	}
	return result
}
