package credentialcatalog

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestBundledDefinitionsReferenceTheAuthoritativeMCPCatalog(t *testing.T) {
	mcp := testMCPCatalog(t)

	definitions, err := ParseDefinitions(BundledDefinitionsJSON(), mcp)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}

	service, exists := definitions.Service("context7")
	if !exists || len(service.CredentialRoles) != 1 ||
		service.CredentialRoles[0].ID != "api-key" ||
		service.Source.Kind != SourceMCPProfile ||
		service.Source.ServerID != "context7" ||
		service.Source.ProfileID != "remote-api-key" {
		t.Fatalf("Context7 definition = %#v, %v", service, exists)
	}
}

func TestParseInstancesSupportsDistinctInstancesAndAdvisoryRequirements(t *testing.T) {
	definitions := testDefinitions(t)
	instances, err := ParseInstances(distinctInstancesPayload(), definitions)
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}

	matches := instances.ForService("dokploy")
	if len(matches) != 2 || matches[0].ID != "dokploy-home" ||
		matches[1].ID != "dokploy-work" {
		t.Fatalf("Dokploy instances = %#v", matches)
	}
	requirement := matches[0].Credentials[1].Requirements[0]
	if requirement.Action != ActionObtain ||
		requirement.InstanceID != "dokploy-home" ||
		requirement.RoleID != "admin-login" {
		t.Fatalf("requirement = %#v", requirement)
	}
}

func distinctInstancesPayload() []byte {
	return []byte(`{
		"schema_version": 1,
		"kind": "mainframe-credential-instances",
		"instances": [
			{
				"id": "dokploy-home",
				"service_id": "dokploy",
				"name": "Home",
				"purpose": "Personal deployments",
				"locator": "home.example.test",
				"credentials": [
					{
						"role_id": "admin-login",
						"secret": {"backend": "secret-env", "name": "DOKPLOY_HOME_ADMIN"}
					},
					{
						"role_id": "api-key",
						"secret": {"backend": "secret-env", "name": "DOKPLOY_HOME_API"},
						"requirements": [
							{
								"action": "obtain",
								"instance_id": "dokploy-home",
								"role_id": "admin-login",
								"summary": "Sign in as the home administrator."
							}
						]
					}
				]
			},
			{
				"id": "dokploy-work",
				"service_id": "dokploy",
				"name": "Work production",
				"purpose": "Company production deployments",
				"locator": "work.example.test",
				"credentials": [
					{
						"role_id": "api-key",
						"secret": {"backend": "secret-env", "name": "DOKPLOY_WORK_API"}
					}
				]
			}
		]
	}`)
}

func TestParseDefinitionsRejectsDriftAndDuplicateOwnership(t *testing.T) {
	mcp := testMCPCatalog(t)
	tests := map[string]string{
		"unknown field": strings.Replace(
			string(BundledDefinitionsJSON()),
			`"kind": "mainframe-credential-definitions"`,
			`"kind": "mainframe-credential-definitions", "extra": true`,
			1,
		),
		"missing MCP source": strings.Replace(
			string(BundledDefinitionsJSON()),
			`"server_id": "context7"`,
			`"server_id": "absent"`,
			1,
		),
		"duplicate service": strings.Replace(
			string(BundledDefinitionsJSON()),
			`"services": [`,
			`"services": [
				{"id":"context7","name":"Duplicate","summary":"Duplicate definition.",
			 "source":{"kind":"mcp-profile","server_id":"context7","profile_id":"remote-api-key"},
			 "credential_roles":[{"id":"api-key","name":"API key","purpose":"Duplicate role.",
			 "acquisition":"Use the source instructions."}]},`,
			1,
		),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := ParseDefinitions([]byte(payload), mcp); err == nil {
				t.Fatal("ParseDefinitions() accepted an invalid catalog")
			}
		})
	}
}

func TestParseInstancesRejectsInvalidReferencesAndGraphs(t *testing.T) {
	definitions := testDefinitions(t)
	valid := `{
		"schema_version": 1,
		"kind": "mainframe-credential-instances",
		"instances": [{
			"id": "dokploy-home",
			"service_id": "dokploy",
			"name": "Home",
			"purpose": "Personal deployments",
			"locator": "home.example.test",
			"credentials": [
				{"role_id":"admin-login","secret":{"backend":"secret-env","name":"DOKPLOY_ADMIN"}},
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"DOKPLOY_API"},
				 "requirements":[{"action":"obtain","instance_id":"dokploy-home",
				 "role_id":"admin-login","summary":"Sign in as administrator."}]}
			]
		}]
	}`
	tests := map[string]string{
		"unsupported version": strings.Replace(valid, `"schema_version": 1`, `"schema_version": 2`, 1),
		"unknown field":       strings.Replace(valid, `"locator":`, `"extra":true,"locator":`, 1),
		"unknown service":     strings.Replace(valid, `"service_id": "dokploy"`, `"service_id": "missing"`, 1),
		"unknown role":        strings.Replace(valid, `"role_id":"api-key"`, `"role_id":"missing"`, 1),
		"invalid secret name": strings.Replace(valid, `"name":"DOKPLOY_API"`, `"name":"literal-value"`, 1),
		"dangling requirement": strings.Replace(
			valid,
			`"instance_id":"dokploy-home"`,
			`"instance_id":"dokploy-missing"`,
			1,
		),
		"self requirement": strings.Replace(
			valid,
			`"role_id":"admin-login","summary":"Sign in as administrator."`,
			`"role_id":"api-key","summary":"Use itself."`,
			1,
		),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := ParseInstances([]byte(payload), definitions); err == nil {
				t.Fatal("ParseInstances() accepted invalid user state")
			}
		})
	}
}

func TestParseInstancesRejectsRequirementCycles(t *testing.T) {
	definitions := testDefinitions(t)
	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[{
			"id":"dokploy-home",
			"service_id":"dokploy",
			"name":"Home",
			"purpose":"Personal deployments",
			"locator":"home.example.test",
			"credentials":[
				{"role_id":"admin-login","secret":{"backend":"secret-env","name":"DOKPLOY_ADMIN"},
				 "requirements":[{"action":"recover","instance_id":"dokploy-home",
				 "role_id":"api-key","summary":"Recover through the API."}]},
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"DOKPLOY_API"},
				 "requirements":[{"action":"obtain","instance_id":"dokploy-home",
				 "role_id":"admin-login","summary":"Sign in as administrator."}]}
			]
		}]
	}`)

	if _, err := ParseInstances(payload, definitions); err == nil ||
		!strings.Contains(err.Error(), "cycle") {
		t.Fatalf("ParseInstances() error = %v, want cycle rejection", err)
	}
}

func TestParseInstancesAcceptsEmptyUserState(t *testing.T) {
	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[]
	}`)

	instances, err := ParseInstances(payload, testDefinitions(t))
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}
	if len(instances.All()) != 0 {
		t.Fatalf("Instances.All() = %#v, want empty", instances.All())
	}
}

func TestParsersRejectOversizedDocuments(t *testing.T) {
	payload := make([]byte, maximumDocumentSize+1)

	if _, err := ParseDefinitions(payload, mcpcatalog.Catalog{}); err == nil ||
		!strings.Contains(err.Error(), "size limit") {
		t.Fatalf("ParseDefinitions() error = %v, want size limit", err)
	}
	if _, err := ParseInstances(payload, Definitions{}); err == nil ||
		!strings.Contains(err.Error(), "size limit") {
		t.Fatalf("ParseInstances() error = %v, want size limit", err)
	}
}

func TestParseInstancesRejectsInvalidAndDuplicateRequirements(t *testing.T) {
	definitions := testDefinitions(t)
	valid := `{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[{
			"id":"dokploy-home",
			"service_id":"dokploy",
			"name":"Home",
			"purpose":"Personal deployments",
			"credentials":[
				{"role_id":"admin-login","secret":{"backend":"secret-env","name":"DOKPLOY_ADMIN"}},
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"DOKPLOY_API"},
				 "requirements":[{"action":"obtain","instance_id":"dokploy-home",
				 "role_id":"admin-login","summary":"Sign in as administrator."}]}
			]
		}]
	}`
	tests := map[string]string{
		"invalid action": strings.Replace(valid, `"action":"obtain"`, `"action":"delegate"`, 1),
		"duplicate requirement": strings.Replace(
			valid,
			`"requirements":[`,
			`"requirements":[
				{"action":"obtain","instance_id":"dokploy-home",
				 "role_id":"admin-login","summary":"Different explanation."},`,
			1,
		),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := ParseInstances([]byte(payload), definitions); err == nil {
				t.Fatal("ParseInstances() accepted invalid requirements")
			}
		})
	}
}

func TestParseInstancesRejectsMissingOrNullInstances(t *testing.T) {
	definitions := testDefinitions(t)
	payloads := []string{
		`{"schema_version":1,"kind":"mainframe-credential-instances"}`,
		`{"schema_version":1,"kind":"mainframe-credential-instances","instances":null}`,
	}
	for _, payload := range payloads {
		if _, err := ParseInstances([]byte(payload), definitions); err == nil {
			t.Fatalf("ParseInstances() accepted %s", payload)
		}
	}
}

func TestDefinitionsRejectControlCharacters(t *testing.T) {
	payload := strings.Replace(
		string(BundledDefinitionsJSON()),
		`"name": "Context7"`,
		`"name": "Context7\u001b[2J"`,
		1,
	)
	if _, err := ParseDefinitions([]byte(payload), testMCPCatalog(t)); err == nil {
		t.Fatal("ParseDefinitions() accepted terminal control characters")
	}
}

func TestCatalogAccessorsReturnIndependentCopies(t *testing.T) {
	definitions := testDefinitions(t)
	services := definitions.Services()
	services[0].Name = "Changed"
	services[0].CredentialRoles[0].Name = "Changed"

	service, _ := definitions.Service("dokploy")
	if service.Name == "Changed" || service.CredentialRoles[0].Name == "Changed" {
		t.Fatalf("Definitions were mutated through Services(): %#v", service)
	}

	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[{
			"id":"dokploy-home",
			"service_id":"dokploy",
			"name":"Home",
			"purpose":"Personal deployments",
			"credentials":[
				{"role_id":"admin-login","secret":{"backend":"secret-env","name":"DOKPLOY_ADMIN"}},
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"DOKPLOY_API"},
				 "requirements":[{"action":"use","instance_id":"dokploy-home",
				 "role_id":"admin-login","summary":"Use the administrator login."}]}
			]
		}]
	}`)
	instances, err := ParseInstances(payload, definitions)
	if err != nil {
		t.Fatalf("ParseInstances() error = %v", err)
	}
	all := instances.All()
	all[0].Name = "Changed"
	all[0].Credentials[1].Requirements[0].Summary = "Changed"

	fresh := instances.All()
	if fresh[0].Name == "Changed" ||
		fresh[0].Credentials[1].Requirements[0].Summary == "Changed" {
		t.Fatalf("Instances were mutated through All(): %#v", fresh[0])
	}
}

func testDefinitions(t *testing.T) Definitions {
	t.Helper()
	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-definitions",
		"services":[{
			"id":"dokploy",
			"name":"Dokploy",
			"summary":"Self-hosted deployment control plane.",
			"source":{"kind":"standalone"},
			"credential_roles":[
				{"id":"admin-login","name":"Administrator login",
				 "purpose":"Manage the selected Dokploy instance.",
				 "acquisition":"Created by the instance owner."},
				{"id":"api-key","name":"API key",
				 "purpose":"Call the selected Dokploy instance API.",
				 "acquisition":"Create it from an administrator session."}
			]
		}]
	}`)
	definitions, err := ParseDefinitions(payload, mcpcatalog.Catalog{})
	if err != nil {
		t.Fatalf("ParseDefinitions() fixture error = %v", err)
	}
	return definitions
}

func testMCPCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatal(err)
	}
	return catalog
}
