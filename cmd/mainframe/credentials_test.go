package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type credentialsContract struct {
	SchemaVersion      int                   `json:"schema_version"`
	Kind               string                `json:"kind"`
	SecretAvailability string                `json:"secret_availability"`
	Services           []credentialsService  `json:"services"`
	Instances          []credentialsInstance `json:"instances"`
}

type credentialsService struct {
	ID string `json:"id"`
}

type credentialsInstance struct {
	ID          string                  `json:"id"`
	ServiceID   string                  `json:"service_id"`
	Credentials []credentialsCredential `json:"credentials"`
}

type credentialsCredential struct {
	Secret credentialsSecretReference `json:"secret"`
}

type credentialsSecretReference struct {
	Backend string `json:"backend"`
	Name    string `json:"name"`
}

func TestCredentialsCommandShowsDefinitionsWhenUserStateIsAbsent(t *testing.T) {
	useCredentialsEnvironment(t)
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"credentials"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var response credentialsContract
	if err := json.Unmarshal(stdout.Bytes(), &response); err != nil {
		t.Fatalf("decode credentials output: %v; output = %q", err, stdout.String())
	}
	if response.SchemaVersion != 1 ||
		response.Kind != "mainframe-credential-catalog" ||
		response.SecretAvailability != "unchecked" {
		t.Fatalf("credentials contract = %#v", response)
	}
	if len(response.Services) != 1 || response.Services[0].ID != "context7" {
		t.Fatalf("services = %#v", response.Services)
	}
	if response.Instances == nil || len(response.Instances) != 0 {
		t.Fatalf("instances = %#v, want non-nil empty list", response.Instances)
	}
	want := `{
  "schema_version": 1,
  "kind": "mainframe-credential-catalog",
  "secret_availability": "unchecked",
  "services": [
    {
      "id": "context7",
      "name": "Context7",
      "summary": "Credential guidance for the verified Context7 MCP profile.",
      "source": {
        "kind": "mcp-profile",
        "server_id": "context7",
        "profile_id": "remote-api-key",
        "credential_kind": "api-key"
      },
      "credential_roles": [
        {
          "id": "api-key",
          "name": "API key",
          "purpose": "Authenticate the selected Context7 remote connection.",
          "acquisition": "Use the authoritative instructions referenced by the Context7 MCP profile."
        }
      ]
    }
  ],
  "instances": []
}
`
	if stdout.String() != want {
		t.Fatalf("credentials output = %q, want %q", stdout.String(), want)
	}
}

func TestCredentialsCommandShowsEveryInstanceWithoutResolvingSecrets(t *testing.T) {
	path := useCredentialsEnvironment(t)
	writeFixtureFile(t, path, []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[
			{"id":"context7-home","service_id":"context7","name":"Home",
			 "purpose":"Personal research","credentials":[
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"CONTEXT7_HOME_KEY"}}
			 ]},
			{"id":"context7-work","service_id":"context7","name":"Work",
			 "purpose":"Company research","credentials":[
				{"role_id":"api-key","secret":{"backend":"secret-env","name":"CONTEXT7_WORK_KEY"}}
			 ]}
		]
	}`), 0o600)
	t.Setenv("CONTEXT7_HOME_KEY", "credential-value-must-not-appear")
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"credentials"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var response credentialsContract
	if err := json.Unmarshal(stdout.Bytes(), &response); err != nil {
		t.Fatalf("decode credentials output: %v", err)
	}
	if len(response.Instances) != 2 ||
		response.Instances[0].ID != "context7-home" ||
		response.Instances[1].ID != "context7-work" {
		t.Fatalf("instances = %#v", response.Instances)
	}
	if response.Instances[0].Credentials[0].Secret.Name != "CONTEXT7_HOME_KEY" {
		t.Fatalf("secret reference = %#v", response.Instances[0].Credentials[0].Secret)
	}
	combined := stdout.String() + stderr.String()
	if strings.Contains(combined, "credential-value-must-not-appear") {
		t.Fatalf("credential value leaked into command output: %q", combined)
	}
}

func TestCredentialsCommandRejectsInvalidUserStateWithoutReflectingIt(t *testing.T) {
	canary := "credential-value-must-not-be-reflected"
	payloads := []string{
		`{
			"schema_version":1,
			"kind":"mainframe-credential-instances",
			"instances":[{"id":"context7-home","service_id":"` + canary + `",
			"name":"Home","purpose":"Personal research","credentials":[]}]
		}`,
		`{
			"schema_version":1,
			"kind":"mainframe-credential-instances",
			"instances":[],
			"` + canary + `":true
		}`,
	}
	for _, payload := range payloads {
		path := useCredentialsEnvironment(t)
		writeFixtureFile(t, path, []byte(payload), 0o600)
		var stdout, stderr bytes.Buffer

		exitCode := run([]string{"credentials"}, strings.NewReader(""), &stdout, &stderr)
		if exitCode != 1 ||
			stderr.String() != "credentials: user instance document is invalid\n" {
			t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
		}
		if stdout.Len() != 0 || strings.Contains(stderr.String(), canary) {
			t.Fatalf(
				"invalid metadata was reflected: stdout=%q stderr=%q",
				stdout.String(),
				stderr.String(),
			)
		}
	}
}

func TestCredentialsCommandRejectsOversizedUserState(t *testing.T) {
	path := useCredentialsEnvironment(t)
	writeFixtureFile(t, path, bytes.Repeat([]byte("x"), (1<<20)+1), 0o600)
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"credentials"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 1 ||
		stderr.String() != "credentials: user instance document is unsafe or unreadable\n" {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestCredentialsCommandRejectsSymlinkedUserState(t *testing.T) {
	path := useCredentialsEnvironment(t)
	target := filepath.Join(t.TempDir(), "instances.json")
	writeFixtureFile(t, target, []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-instances",
		"instances":[]
	}`), 0o600)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, path); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"credentials"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 1 ||
		stderr.String() != "credentials: user instance document is unsafe or unreadable\n" {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestCredentialsCommandRejectsArguments(t *testing.T) {
	var stdout, stderr bytes.Buffer

	exitCode := run(
		[]string{"credentials", "--json"},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)
	if exitCode != 2 ||
		stderr.String() != "credentials does not accept arguments\n" {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func useCredentialsEnvironment(t *testing.T) string {
	t.Helper()
	usePlanRelease(t)
	home := t.TempDir()
	config := filepath.Join(home, "config")
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", config)
	return filepath.Join(config, "credentials", "mainframe", "instances.json")
}
