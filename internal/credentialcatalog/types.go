package credentialcatalog

type ServiceID string
type RoleID string
type InstanceID string
type SourceKind string
type CredentialKind string
type SecretBackend string
type RequirementAction string

const (
	SourceStandalone SourceKind = "standalone"
	SourceMCPProfile SourceKind = "mcp-profile"

	CredentialAPIKey CredentialKind = "api-key"

	BackendSecretEnvironment SecretBackend = "secret-env"

	ActionUse     RequirementAction = "use"
	ActionObtain  RequirementAction = "obtain"
	ActionRotate  RequirementAction = "rotate"
	ActionRecover RequirementAction = "recover"
)

type ServiceDefinition struct {
	ID              ServiceID        `json:"id"`
	Name            string           `json:"name"`
	Summary         string           `json:"summary"`
	Source          SourceReference  `json:"source"`
	CredentialRoles []CredentialRole `json:"credential_roles"`
}

type SourceReference struct {
	Kind           SourceKind     `json:"kind"`
	ServerID       string         `json:"server_id,omitempty"`
	ProfileID      string         `json:"profile_id,omitempty"`
	CredentialKind CredentialKind `json:"credential_kind,omitempty"`
}

type CredentialRole struct {
	ID          RoleID `json:"id"`
	Name        string `json:"name"`
	Purpose     string `json:"purpose"`
	Acquisition string `json:"acquisition"`
}

type Instance struct {
	ID          InstanceID          `json:"id"`
	ServiceID   ServiceID           `json:"service_id"`
	Name        string              `json:"name"`
	Purpose     string              `json:"purpose"`
	Locator     string              `json:"locator,omitempty"`
	Credentials []CredentialBinding `json:"credentials"`
}

type CredentialBinding struct {
	RoleID       RoleID          `json:"role_id"`
	Secret       SecretReference `json:"secret"`
	Requirements []Requirement   `json:"requirements,omitempty"`
}

type SecretReference struct {
	Backend SecretBackend `json:"backend"`
	Name    string        `json:"name"`
}

type SecretUse struct {
	InstanceID   InstanceID
	ServiceID    ServiceID
	InstanceName string
	RoleID       RoleID
}

type Requirement struct {
	Action     RequirementAction `json:"action"`
	InstanceID InstanceID        `json:"instance_id"`
	RoleID     RoleID            `json:"role_id"`
	Summary    string            `json:"summary"`
}

type Definitions struct {
	services []ServiceDefinition
}

type Instances struct {
	instances []Instance
}

func (definitions Definitions) Services() []ServiceDefinition {
	return cloneServices(definitions.services)
}

func (definitions Definitions) Service(id ServiceID) (ServiceDefinition, bool) {
	for _, service := range definitions.services {
		if service.ID == id {
			return cloneService(service), true
		}
	}
	return ServiceDefinition{}, false
}

func (instances Instances) All() []Instance {
	return cloneInstances(instances.instances)
}

func (instances Instances) Clone() Instances {
	return Instances{instances: instances.All()}
}

func (instances Instances) ForService(id ServiceID) []Instance {
	var matches []Instance
	for _, instance := range instances.instances {
		if instance.ServiceID == id {
			matches = append(matches, cloneInstance(instance))
		}
	}
	return matches
}

func (instances Instances) Uses(reference SecretReference) []SecretUse {
	var uses []SecretUse
	for _, instance := range instances.instances {
		for _, credential := range instance.Credentials {
			if credential.Secret == reference {
				uses = append(uses, SecretUse{
					InstanceID: instance.ID, ServiceID: instance.ServiceID,
					InstanceName: instance.Name, RoleID: credential.RoleID,
				})
			}
		}
	}
	return uses
}

func cloneServices(source []ServiceDefinition) []ServiceDefinition {
	result := make([]ServiceDefinition, len(source))
	for index, service := range source {
		result[index] = cloneService(service)
	}
	return result
}

func cloneService(source ServiceDefinition) ServiceDefinition {
	source.CredentialRoles = append([]CredentialRole(nil), source.CredentialRoles...)
	return source
}

func cloneInstances(source []Instance) []Instance {
	result := make([]Instance, len(source))
	for index, instance := range source {
		result[index] = cloneInstance(instance)
	}
	return result
}

func cloneInstance(source Instance) Instance {
	credentials := source.Credentials
	source.Credentials = make([]CredentialBinding, len(credentials))
	for index, credential := range credentials {
		cloned := credential
		cloned.Requirements = append(
			[]Requirement(nil),
			credential.Requirements...,
		)
		source.Credentials[index] = cloned
	}
	return source
}

func (instance Instance) Clone() Instance {
	return cloneInstance(instance)
}
