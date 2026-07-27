package mcpconfiguration_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

const keyedDesired = `{"headers":{"CONTEXT7_API_KEY":"{env:CUSTOM_CONTEXT7_KEY}"},"type":"remote","url":"https://mcp.context7.com/mcp"}`

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
	tests := []struct {
		name       string
		config     string
		registry   string
		bind       bool
		selections []mcpcatalog.Selection
		want       string
		absent     []string
	}{
		{
			name: "keyless to keyed", config: `{"mcp":{"context7":` + desired + `}}`,
			registry: owned(desired), bind: true, selections: keyedOpenCodeSelection(),
			want: `{env:CUSTOM_CONTEXT7_KEY}`, absent: []string{"raw-secret-must-not-appear"},
		},
		{
			name: "keyed to keyless", config: `{"mcp":{"context7":` + keyedDesired + `}}`,
			registry: owned(keyedDesired), selections: openCodeSelection(),
			want:   `"url": "https://mcp.context7.com/mcp"`,
			absent: []string{"headers", "CONTEXT7_API_KEY", "CUSTOM_CONTEXT7_KEY"},
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
			prepared, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentOpenCode}, test.selections,
			)
			if err != nil {
				t.Fatalf("Prepare() error = %v", err)
			}
			mutations := prepared.Transitions()[0].Mutations
			if len(mutations) != 2 {
				t.Fatalf("mutations = %#v", mutations)
			}
			for _, mutation := range mutations {
				after := string(mutation.After.Content)
				if !strings.Contains(after, test.want) {
					t.Fatalf("after-image lacks %q:\n%s", test.want, after)
				}
				for _, absent := range test.absent {
					if strings.Contains(after, absent) {
						t.Fatalf("after-image contains stale or secret value %q:\n%s", absent, after)
					}
				}
			}
		})
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
