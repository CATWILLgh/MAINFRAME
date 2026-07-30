package mcpconfiguration_test

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestScanManagedSecretReferencesEnumeratesFixedRegistriesDeterministically(
	t *testing.T,
) {
	host := managedSecretReferenceHost()

	got, err := mcpconfiguration.ScanManagedSecretReferences(host)
	if err != nil {
		t.Fatalf("ScanManagedSecretReferences() error = %v", err)
	}
	want := managedSecretReferenceWant()
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("references = %#v, want %#v", got, want)
	}
	if host.reads != 4 {
		t.Fatalf("registry reads = %d, want 4", host.reads)
	}
}

func managedSecretReferenceHost() *fakeHost {
	return &fakeHost{entries: map[domain.Location]hostfs.Entry{
		managedRegistry(domain.RootClaudeConfig, "mainframe/mcp-ownership.json"): regular(
			`{"version":1,"servers":{"plain":{"type":"http","url":"https://example.test"}}}`,
		),
		managedRegistry(domain.RootCodexConfig, "mainframe/mcp-ownership.json"): regular(
			`{"version":1,"servers":{"retired":null}}`,
		),
		managedRegistry(
			domain.RootOpenCodeConfig,
			"opencode.json.mainframe-mcp.json",
		): regular(`{"version":1,"servers":{
			"zeta":{"format":"opencode-file-secret-v1","profile":"remote-api-key","secret_backend":"environment","secret_reference":"SHARED_KEY","entry":{"type":"remote","url":"https://example.test"},"secret_file_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
			"plain":{"type":"remote","url":"https://example.test"}
		}}`),
		managedRegistry(
			domain.RootAntigravityData,
			"mainframe/mcp-ownership.json",
		): regular(`{"version":1,"servers":{
			"zeta":{"format":"antigravity-literal-secret-v1","profile":"remote-api-key","secret_backend":"environment","secret_reference":"SECOND_KEY","entry_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
			"alpha":{"format":"antigravity-literal-secret-v1","profile":"remote-api-key","secret_backend":"environment","secret_reference":"SHARED_KEY","entry_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}
		}}`),
	}}
}

func managedSecretReferenceWant() []mcpconfiguration.ManagedSecretReference {
	return []mcpconfiguration.ManagedSecretReference{
		{
			Reference: "SHARED_KEY", ComponentID: domain.ComponentAntigravity2,
			ResourceID: "alpha",
			RegistryTarget: managedRegistry(
				domain.RootAntigravityData,
				"mainframe/mcp-ownership.json",
			),
		},
		{
			Reference: "SECOND_KEY", ComponentID: domain.ComponentAntigravity2,
			ResourceID: "zeta",
			RegistryTarget: managedRegistry(
				domain.RootAntigravityData,
				"mainframe/mcp-ownership.json",
			),
		},
		{
			Reference: "SHARED_KEY", ComponentID: domain.ComponentOpenCode,
			ResourceID: "zeta",
			RegistryTarget: managedRegistry(
				domain.RootOpenCodeConfig,
				"opencode.json.mainframe-mcp.json",
			),
		},
	}
}

func TestScanManagedSecretReferencesAllowsMissingRegistriesAndTombstones(
	t *testing.T,
) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		managedRegistry(
			domain.RootOpenCodeConfig,
			"opencode.json.mainframe-mcp.json",
		): regular(`{"version":1,"servers":{"retired":null}}`),
	}}

	got, err := mcpconfiguration.ScanManagedSecretReferences(host)
	if err != nil {
		t.Fatalf("ScanManagedSecretReferences() error = %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("references = %#v, want none", got)
	}
}

func TestScanManagedSecretReferencesFailsClosed(t *testing.T) {
	var absentHost mcpconfiguration.Host
	if _, err := mcpconfiguration.ScanManagedSecretReferences(absentHost); err == nil {
		t.Fatal("nil host was accepted")
	}
	openCodeTarget := managedRegistry(
		domain.RootOpenCodeConfig,
		"opencode.json.mainframe-mcp.json",
	)
	tests := []struct {
		name string
		host *fakeHost
	}{
		{
			name: "inspection failure",
			host: &fakeHost{failures: map[domain.Location]error{
				openCodeTarget: errors.New("denied"),
			}},
		},
		{
			name: "unsafe registry kind",
			host: &fakeHost{entries: map[domain.Location]hostfs.Entry{
				openCodeTarget: {Kind: hostfs.EntrySymlink},
			}},
		},
		{
			name: "malformed document",
			host: &fakeHost{entries: map[domain.Location]hostfs.Entry{
				openCodeTarget: regular(`{"version":1,"servers":`),
			}},
		},
		{
			name: "malformed recognized secret schema",
			host: &fakeHost{entries: map[domain.Location]hostfs.Entry{
				openCodeTarget: regular(`{"version":1,"servers":{"context7":{
					"format":"opencode-file-secret-v1",
					"secret_reference":"CUSTOM_KEY"
				}}}`),
			}},
		},
		{
			name: "unknown secret-bearing entry",
			host: &fakeHost{entries: map[domain.Location]hostfs.Entry{
				openCodeTarget: regular(`{"version":1,"servers":{"context7":{
					"format":"future-secret-v2",
					"secret_reference":"CUSTOM_KEY"
				}}}`),
			}},
		},
		{
			name: "nested unknown secret-bearing entry",
			host: &fakeHost{entries: map[domain.Location]hostfs.Entry{
				openCodeTarget: regular(`{"version":1,"servers":{"context7":{
					"format":"future-secret-v2",
					"metadata":[{"credentials":{"secret_reference":"CUSTOM_KEY"}}]
				}}}`),
			}},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := mcpconfiguration.ScanManagedSecretReferences(test.host); err == nil {
				t.Fatal("unsafe managed registry state was accepted")
			}
		})
	}
}

func TestScanManagedSecretReferencesDoesNotExposeEnvironmentValues(t *testing.T) {
	const canary = "raw-secret-must-not-appear"
	t.Setenv("CUSTOM_KEY", canary)
	target := managedRegistry(
		domain.RootOpenCodeConfig,
		"opencode.json.mainframe-mcp.json",
	)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: regular(`{"version":1,"servers":{"context7":{
			"format":"opencode-file-secret-v1",
			"profile":"remote-api-key",
			"secret_backend":"environment",
			"secret_reference":"CUSTOM_KEY",
			"entry":{"type":"remote","url":"https://example.test"},
			"secret_file_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
		}}}`),
	}}

	got, err := mcpconfiguration.ScanManagedSecretReferences(host)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(strings.TrimSpace(renderReferences(got)), canary) {
		t.Fatal("secret value escaped through reference scan")
	}
}

func managedRegistry(
	root domain.RootID,
	path domain.ArtifactPath,
) domain.Location {
	return domain.Location{Root: root, Path: path}
}

func regular(content string) hostfs.Entry {
	return hostfs.Entry{
		Kind:    hostfs.EntryRegular,
		Content: []byte(content),
	}
}

func renderReferences(references []mcpconfiguration.ManagedSecretReference) string {
	var result strings.Builder
	for _, reference := range references {
		result.WriteString(reference.Reference)
		result.WriteString(string(reference.ComponentID))
		result.WriteString(reference.ResourceID)
	}
	return result.String()
}
