package mcpconfiguration_test

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

const keyedDesired = `{"headers":{"CONTEXT7_API_KEY":"{file:mainframe/secrets/context7-api-key}"},"type":"remote","url":"https://mcp.context7.com/mcp"}`

type openCodeCredentialPreparationCase struct {
	name       string
	config     string
	registry   string
	bind       bool
	selections []mcpcatalog.Selection
	want       string
	absent     []string
	mutations  int
}

func TestOpenCodeCredentialBindingReconcilesProfileChangesAsOwnedUpdates(t *testing.T) {
	tests := []struct {
		name       string
		config     string
		registry   string
		bind       bool
		selections []mcpcatalog.Selection
	}{
		{
			name: "keyless to keyed", config: `{"mcp":{"context7":` + desired + `}}`,
			registry: owned(desired), bind: true, selections: keyedOpenCodeSelection(),
		},
		{
			name: "keyed to keyless", config: `{"mcp":{"context7":` + keyedDesired + `}}`,
			registry: owned(keyedDesired), selections: openCodeSelection(),
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			inspection := inspectOpenCodePrepared(
				t, openCodePreparedHost([]byte(test.config), []byte(test.registry)),
			)
			if test.bind {
				inspection = bindOpenCodeCredential(t, inspection)
			}
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentOpenCode}, test.selections,
			)
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			if plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentUpdate ||
				plan.Intents[0].ProjectionID != "opencode.mcp.context7" ||
				plan.Intents[0].Target != location("opencode.json") {
				t.Fatalf("profile transition plan = %#v", plan)
			}
		})
	}
}

func TestPrepareOpenCodeCredentialBindingAddsReferenceAndRemovesStaleHeaders(t *testing.T) {
	t.Setenv("CUSTOM_CONTEXT7_KEY", "raw-secret-must-not-appear")
	tests := []openCodeCredentialPreparationCase{
		{
			name: "keyless to keyed", config: `{"mcp":{"context7":` + desired + `}}`,
			registry: owned(desired), bind: true, selections: keyedOpenCodeSelection(),
			want:      `{file:mainframe/secrets/context7-api-key}`,
			absent:    []string{"raw-secret-must-not-appear", "CUSTOM_CONTEXT7_KEY"},
			mutations: 3,
		},
		{
			name: "keyed to keyless", config: `{"mcp":{"context7":` + keyedDesired + `}}`,
			registry: owned(keyedDesired), selections: openCodeSelection(),
			want:      `"url": "https://mcp.context7.com/mcp"`,
			absent:    []string{"headers", "CONTEXT7_API_KEY", "CUSTOM_CONTEXT7_KEY"},
			mutations: 2,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			assertOpenCodeCredentialPreparation(t, test)
		})
	}
}

func assertOpenCodeCredentialPreparation(
	t *testing.T,
	test openCodeCredentialPreparationCase,
) {
	t.Helper()
	inspection := inspectOpenCodePrepared(
		t,
		openCodePreparedHost([]byte(test.config), []byte(test.registry)),
	)
	if test.bind {
		inspection = bindOpenCodeCredential(t, inspection)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode},
		test.selections,
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != test.mutations {
		t.Fatalf("mutations = %#v", mutations)
	}
	for _, mutation := range mutations {
		assertOpenCodeCredentialMutation(t, mutation, test)
	}
}

func assertOpenCodeCredentialMutation(
	t *testing.T,
	mutation configuration.FileMutation,
	test openCodeCredentialPreparationCase,
) {
	t.Helper()
	after := string(mutation.After.Content)
	if mutation.Target != location("opencode.json") {
		if strings.Contains(after, "raw-secret-must-not-appear") {
			t.Fatal("prepared plan contains a resolved secret")
		}
		return
	}
	if !strings.Contains(after, test.want) {
		t.Fatalf("after-image lacks %q:\n%s", test.want, after)
	}
	for _, absent := range test.absent {
		if strings.Contains(after, absent) {
			t.Fatalf(
				"after-image contains stale or secret value %q:\n%s",
				absent,
				after,
			)
		}
	}
}

func TestOpenCodeCredentialBindingFailsClosedForInvalidScopeAndEnvironment(t *testing.T) {
	inspection := inspectOpenCodePrepared(t, openCodePreparedHost(nil, nil))
	tests := []mcpconfiguration.CredentialBinding{
		{
			ComponentID: domain.ComponentOpenCode, ServerID: "context7",
			ProfileID: "remote-api-key", EnvironmentVariable: "CUSTOM-CONTEXT7-KEY",
		},
		{
			ComponentID: domain.ComponentClaudeCode, ServerID: "context7",
			ProfileID: "remote-api-key", EnvironmentVariable: "CUSTOM_CONTEXT7_KEY",
		},
		{
			ComponentID: domain.ComponentCodex, ServerID: "context7",
			ProfileID: "remote-api-key", EnvironmentVariable: "CUSTOM_CONTEXT7_KEY",
		},
		{
			ComponentID: domain.ComponentAntigravity2, ServerID: "context7",
			ProfileID: "remote-api-key", EnvironmentVariable: "CUSTOM_CONTEXT7_KEY",
		},
	}
	for _, binding := range tests {
		if _, err := inspection.WithCredentialBindings(
			[]mcpconfiguration.CredentialBinding{binding},
		); err == nil {
			t.Fatalf("unsafe credential binding was accepted: %#v", binding)
		}
	}
}

func TestOpenCodePrivateCredentialDriftRelinquishesWithoutSecretDisclosure(
	t *testing.T,
) {
	const expected = "test-private-value"
	registry := openCodeSecretRegistry(keyedDesired, expected)
	tests := []struct {
		name  string
		entry hostfs.Entry
	}{
		{
			name:  "content changed",
			entry: preparedOpenCodeEntry([]byte("changed"), 0o600, 103),
		},
		{
			name:  "permissions widened",
			entry: preparedOpenCodeEntry([]byte(expected), 0o644, 103),
		},
		{
			name:  "symbolic link",
			entry: hostfs.Entry{Kind: hostfs.EntrySymlink},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := openCodePreparedHost(
				[]byte(`{"mcp":{"context7":`+keyedDesired+`}}`),
				[]byte(registry),
			)
			host.entries[projection().SecretTarget()] = test.entry
			inspection := bindOpenCodeCredential(
				t,
				inspectOpenCodePrepared(t, host),
			)
			plan, err := inspection.Plan(
				[]domain.ComponentID{domain.ComponentOpenCode},
				keyedOpenCodeSelection(),
			)
			if err != nil {
				t.Fatal(err)
			}
			if plan.Blocking || len(plan.Intents) != 1 ||
				plan.Intents[0].Kind != mcpconfiguration.IntentRelinquish {
				t.Fatalf("plan = %#v", plan)
			}
			if strings.Contains(fmt.Sprintf("%#v", plan), expected) {
				t.Fatal("plan exposes private credential content")
			}
		})
	}
}

func TestOpenCodePrivateCredentialMaterializesOnlyIntoItsFile(t *testing.T) {
	host := openCodePreparedHost(
		[]byte(`{"mcp":{"context7":`+keyedDesired+`}}`),
		[]byte(openCodeSecretRegistry(keyedDesired, "old-value")),
	)
	host.entries[projection().SecretTarget()] = preparedOpenCodeEntry(
		[]byte("old-value"),
		0o600,
		103,
	)
	inspection := bindOpenCodeCredential(t, inspectOpenCodePrepared(t, host))
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode},
		keyedOpenCodeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	materialized, err := prepared.MaterializeSecrets(
		staticSecretResolver("new-value"),
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, transition := range materialized.Transitions() {
		for _, mutation := range transition.Mutations {
			content := string(mutation.After.Content)
			if mutation.Target == projection().SecretTarget() {
				if content != "new-value" || mutation.After.Mode != 0o600 {
					t.Fatal("private credential file was not materialized exactly")
				}
				continue
			}
			if strings.Contains(content, "new-value") {
				t.Fatalf("secret escaped into %v", mutation.Target)
			}
		}
	}
}

type staticSecretResolver string

func (resolver staticSecretResolver) ResolveSecret(string) (string, error) {
	return string(resolver), nil
}

func openCodeSecretRegistry(entry string, secret string) string {
	sum := sha256.Sum256([]byte(secret))
	return fmt.Sprintf(
		`{"version":1,"servers":{"context7":{"format":"opencode-file-secret-v1","profile":"remote-api-key","secret_backend":"environment","secret_reference":"CUSTOM_CONTEXT7_KEY","entry":%s,"secret_file_sha256":"%s"}}}`,
		entry,
		hex.EncodeToString(sum[:]),
	)
}

var _ configuration.SecretResolver = staticSecretResolver("")

func bindOpenCodeCredential(
	t *testing.T,
	inspection mcpconfiguration.Inspection,
) mcpconfiguration.Inspection {
	t.Helper()
	bound, err := inspection.WithCredentialBindings(
		[]mcpconfiguration.CredentialBinding{{
			ComponentID: domain.ComponentOpenCode, ServerID: "context7",
			ProfileID: "remote-api-key", EnvironmentVariable: "CUSTOM_CONTEXT7_KEY",
		}},
	)
	if err != nil {
		t.Fatalf("WithCredentialBindings() error = %v", err)
	}
	return bound
}

func keyedOpenCodeSelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-api-key",
		Adapters: []domain.ComponentID{domain.ComponentOpenCode},
	}}
}
