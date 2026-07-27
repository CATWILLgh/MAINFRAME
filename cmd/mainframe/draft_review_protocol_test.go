package main

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestDecodeDraftReviewRequestAcceptsCredentialReferencesOnly(t *testing.T) {
	request, err := decodeDraftReviewRequest(strings.NewReader(`{
		"schema_version": 1,
		"kind": "mainframe-draft",
		"desired": {
			"adapters": ["opencode"],
			"diagnostics_policy": "preserve-retained-adapters",
			"mcp": [{
				"server_id": "context7",
				"profile_id": "remote-api-key",
				"adapters": ["opencode"],
				"credential_instance_id": "context7-home"
			}]
		}
	}`))
	if err != nil {
		t.Fatalf("decodeDraftReviewRequest() error = %v", err)
	}
	if request.Desired.MCP[0].CredentialInstanceID != "context7-home" {
		t.Fatalf("request = %#v", request)
	}
}

func TestDecodeDraftReviewRequestRejectsAmbiguousOrSecretBearingInput(
	t *testing.T,
) {
	tests := []struct {
		name    string
		payload string
	}{
		{name: "null", payload: `null`},
		{
			name:    "wrong version",
			payload: `{"schema_version":2,"kind":"mainframe-draft","desired":{"adapters":[],"mcp":[],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
		{
			name:    "wrong kind",
			payload: `{"schema_version":1,"kind":"other","desired":{"adapters":[],"mcp":[],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
		{
			name:    "missing adapters",
			payload: `{"schema_version":1,"kind":"mainframe-draft","desired":{"mcp":[],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
		{
			name:    "missing mcp",
			payload: `{"schema_version":1,"kind":"mainframe-draft","desired":{"adapters":[],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
		{
			name:    "secret value",
			payload: `{"schema_version":1,"kind":"mainframe-draft","desired":{"adapters":["opencode"],"mcp":[{"server_id":"context7","profile_id":"remote-api-key","adapters":["opencode"],"secret_value":"must-not-be-accepted"}],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
		{
			name:    "duplicate key",
			payload: `{"schema_version":1,"schema_version":1,"kind":"mainframe-draft","desired":{"adapters":[],"mcp":[],"diagnostics_policy":"preserve-retained-adapters"}}`,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := decodeDraftReviewRequest(
				strings.NewReader(test.payload),
			); err == nil {
				t.Fatal("invalid draft request was accepted")
			}
		})
	}
}

func TestNormalizeDraftReviewRequestUsesCatalogAndSortsDesiredState(
	t *testing.T,
) {
	request := draftReviewRequest{
		SchemaVersion: 1,
		Kind:          draftRequestKind,
		Desired: draftDesiredState{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters: []domain.ComponentID{
				domain.ComponentOpenCode,
			},
			MCP: []draftMCPSelection{{
				ServerID:             "context7",
				ProfileID:            "remote-api-key",
				Adapters:             []domain.ComponentID{domain.ComponentOpenCode},
				CredentialInstanceID: "context7-home",
			}},
		},
	}

	normalized, internal, onboarding, err := normalizeDraftReviewRequest(
		credentialMCPApplyCatalog(t),
		request,
	)
	if err != nil {
		t.Fatalf("normalizeDraftReviewRequest() error = %v", err)
	}
	expected := application.Request{
		Components: []domain.ComponentID{domain.ComponentOpenCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		}},
		MCPCredentials: []application.MCPCredentialBinding{{
			ComponentID: domain.ComponentOpenCode,
			ServerID:    "context7", ProfileID: "remote-api-key",
			InstanceID: credentialcatalog.InstanceID("context7-home"),
		}},
	}
	if !reflect.DeepEqual(internal, expected) {
		t.Fatalf("application request = %#v, want %#v", internal, expected)
	}
	if !reflect.DeepEqual(normalized, request.Desired) {
		t.Fatalf("normalized desired = %#v", normalized)
	}
	if len(onboarding.Connections) != 1 {
		t.Fatalf("onboarding = %#v", onboarding)
	}
}

func TestNormalizeDraftReviewRequestRejectsDuplicateAndUnsupportedChoices(
	t *testing.T,
) {
	catalog := credentialMCPApplyCatalog(t)
	tests := []draftDesiredState{
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters: []domain.ComponentID{
				domain.ComponentOpenCode,
				domain.ComponentOpenCode,
			},
			MCP: []draftMCPSelection{},
		},
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
			MCP: []draftMCPSelection{{
				ServerID: "missing", ProfileID: "remote-api-key",
				Adapters: []domain.ComponentID{domain.ComponentOpenCode},
			}},
		},
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
			MCP: []draftMCPSelection{{
				ServerID: "context7", ProfileID: "remote-api-key",
				Adapters:             []domain.ComponentID{domain.ComponentOpenCode},
				CredentialInstanceID: " context7-home",
			}},
		},
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
			MCP: []draftMCPSelection{{
				ServerID: "context7", ProfileID: "remote-api-key",
				Adapters: []domain.ComponentID{domain.ComponentOpenCode},
			}},
		},
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
			MCP: []draftMCPSelection{{
				ServerID: "context7", ProfileID: "remote-keyless",
				Adapters:             []domain.ComponentID{domain.ComponentOpenCode},
				CredentialInstanceID: "context7-home",
			}},
		},
		{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters:          []domain.ComponentID{domain.ComponentClaudeCode},
			MCP: []draftMCPSelection{{
				ServerID: "context7", ProfileID: "remote-api-key",
				Adapters:             []domain.ComponentID{domain.ComponentClaudeCode},
				CredentialInstanceID: "context7-home",
			}},
		},
	}
	for _, desired := range tests {
		request := draftReviewRequest{
			SchemaVersion: 1, Kind: draftRequestKind, Desired: desired,
		}
		if _, _, _, err := normalizeDraftReviewRequest(
			catalog,
			request,
		); err == nil {
			t.Fatalf("invalid desired state was accepted: %#v", desired)
		}
	}
}

func TestNormalizeDraftReviewReusesOneInstanceAcrossAdapters(t *testing.T) {
	request := draftReviewRequest{
		SchemaVersion: 1, Kind: draftRequestKind,
		Desired: draftDesiredState{
			DiagnosticsPolicy: draftDiagnosticsPolicy,
			Adapters: []domain.ComponentID{
				domain.ComponentAntigravity2,
				domain.ComponentOpenCode,
			},
			MCP: []draftMCPSelection{{
				ServerID: "context7", ProfileID: "remote-api-key",
				Adapters: []domain.ComponentID{
					domain.ComponentAntigravity2,
					domain.ComponentOpenCode,
				},
				CredentialInstanceID: "context7-home",
			}},
		},
	}

	_, internal, _, err := normalizeDraftReviewRequest(
		credentialMCPApplyCatalog(t),
		request,
	)
	if err != nil {
		t.Fatalf("normalizeDraftReviewRequest() error = %v", err)
	}
	if len(internal.MCPCredentials) != 2 {
		t.Fatalf("credential bindings = %#v", internal.MCPCredentials)
	}
	for _, binding := range internal.MCPCredentials {
		if binding.InstanceID != "context7-home" {
			t.Fatalf("credential binding = %#v", binding)
		}
	}
}

func TestNormalizeDraftReviewKeepsCompleteEmptyArrays(t *testing.T) {
	request := draftReviewRequest{
		SchemaVersion: 1, Kind: draftRequestKind,
		Desired: draftDesiredState{
			Adapters:          []domain.ComponentID{},
			MCP:               []draftMCPSelection{},
			DiagnosticsPolicy: draftDiagnosticsPolicy,
		},
	}

	normalized, _, _, err := normalizeDraftReviewRequest(
		credentialMCPApplyCatalog(t),
		request,
	)
	if err != nil {
		t.Fatalf("normalizeDraftReviewRequest() error = %v", err)
	}
	if normalized.Adapters == nil || normalized.MCP == nil {
		t.Fatalf("normalized complete arrays = %#v", normalized)
	}
}
