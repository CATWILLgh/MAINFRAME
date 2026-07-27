package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestDraftReviewCommandWritesOnlyTheReviewedResponse(t *testing.T) {
	var stdout, stderr bytes.Buffer
	context := validDraftCommandContext(&stdout, &stderr)
	context.reviewDraft = func(request draftReviewRequest) (
		draftReviewResponse,
		error,
	) {
		return draftReviewResponse{
			SchemaVersion: 1,
			Kind:          draftReviewResponseKind,
			Apply: draftApplyAvailability{
				CommandAvailable: false,
			},
		}, nil
	}

	exitCode := runDraftReviewFromRegistry(context, nil)

	if exitCode != 0 || stderr.Len() != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var response draftReviewResponse
	if err := json.Unmarshal(stdout.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Kind != draftReviewResponseKind ||
		response.Apply.CommandAvailable {
		t.Fatalf("response = %#v", response)
	}
}

func TestDraftReviewCommandNeverReflectsRejectedOrRuntimeInput(t *testing.T) {
	const marker = "raw-secret-must-not-appear"
	tests := []struct {
		name    string
		context func(*bytes.Buffer, *bytes.Buffer) commandContext
	}{
		{
			name: "unknown secret field",
			context: func(stdout, stderr *bytes.Buffer) commandContext {
				return commandContext{
					input: strings.NewReader(`{
						"schema_version":1,
						"kind":"mainframe-draft",
						"desired":{
							"adapters":[],
							"mcp":[],
							"diagnostics_policy":"preserve-retained-adapters",
							"secret_value":"` + marker + `"
						}
					}`),
					output: stdout, errorOutput: stderr,
					reviewDraft: func(
						draftReviewRequest,
					) (draftReviewResponse, error) {
						t.Fatal("reviewer called for rejected input")
						return draftReviewResponse{}, nil
					},
				}
			},
		},
		{
			name: "runtime error",
			context: func(stdout, stderr *bytes.Buffer) commandContext {
				context := validDraftCommandContext(stdout, stderr)
				context.reviewDraft = func(
					draftReviewRequest,
				) (draftReviewResponse, error) {
					return draftReviewResponse{}, errors.New(marker)
				}
				return context
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			exitCode := runDraftReviewFromRegistry(
				test.context(&stdout, &stderr),
				nil,
			)
			if exitCode != 1 || stdout.Len() != 0 ||
				strings.Contains(stderr.String(), marker) {
				t.Fatalf(
					"exit code = %d, stdout = %q, stderr = %q",
					exitCode,
					stdout.String(),
					stderr.String(),
				)
			}
		})
	}
}

func validDraftCommandContext(
	stdout,
	stderr *bytes.Buffer,
) commandContext {
	return commandContext{
		input: strings.NewReader(`{
			"schema_version":1,
			"kind":"mainframe-draft",
			"desired":{
				"adapters":[],
				"mcp":[],
				"diagnostics_policy":"preserve-retained-adapters"
			}
		}`),
		output: stdout, errorOutput: stderr,
	}
}

func TestPublicDraftReviewOmitsExecutablePathsAndSecretMaterial(t *testing.T) {
	const marker = "raw-secret-must-not-appear"
	desired := draftDesiredState{
		DiagnosticsPolicy: draftDiagnosticsPolicy,
		Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
		MCP: []draftMCPSelection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters:             []domain.ComponentID{domain.ComponentOpenCode},
			CredentialInstanceID: "context7-home",
		}},
	}
	preview := lifecycle.Preview{
		Filesystem: domain.Plan{Operations: []domain.Operation{{
			ComponentID: domain.ComponentOpenCode,
			UnitID:      "opencode.bundle",
			Kind:        domain.OperationInstall,
			SourcePath:  domain.ArtifactPath(marker),
			Artifact: domain.Artifact{
				Location: domain.Location{Path: marker},
			},
		}}},
		Configuration: configuration.Plan{
			Changes: []configuration.Change{{
				ResourceID: "opencode.config", ComponentID: domain.ComponentOpenCode,
				Kind: configuration.ChangeUpdate,
			}},
		},
		MCP: mcpconfiguration.Plan{
			Intents: []mcpconfiguration.Intent{{
				ComponentID: domain.ComponentOpenCode,
				ServerID:    "context7", ProfileID: "remote-api-key",
				Kind:   mcpconfiguration.IntentAdd,
				Target: domain.Location{Path: marker},
			}},
		},
		Diagnostics: diagnostics.Plan{
			Intents: []diagnostics.Intent{{
				ComponentID: domain.ComponentOpenCode,
			}},
		},
	}
	response := publicDraftReview(
		desired,
		preview,
		mcpcatalog.OnboardingPreview{
			Connections: []mcpcatalog.Connection{{
				ServerID: "context7", ServerName: "Context7",
				Profile: mcpcatalog.Profile{
					ID: "remote-api-key", Name: "Remote with API key",
					Transport: mcpcatalog.TransportStreamableHTTP,
					Authentication: mcpcatalog.Authentication{
						Kind: mcpcatalog.AuthenticationAPIKey,
					},
				},
				Adapters: []domain.ComponentID{domain.ComponentOpenCode},
			}},
		},
	)

	payload, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("encode response: %v", err)
	}
	text := string(payload)
	for _, forbidden := range []string{
		marker,
		"source_path",
		"target",
		"environment_variable",
	} {
		if strings.Contains(text, forbidden) {
			t.Fatalf("public review contains %q: %s", forbidden, text)
		}
	}
	if !strings.Contains(text, `"command_available":false`) ||
		!strings.Contains(text, `"state_semantics":"complete-desired-state"`) {
		t.Fatalf("public review omits safety contract: %s", text)
	}
}

func TestMachineDraftSnapshotDoesNotStartCodexObservation(t *testing.T) {
	builder := newMachineDraftSnapshotBuilder("/release", "/work")
	if client := builder.client(); client != nil {
		t.Fatalf("machine draft Codex client = %#v, want nil", client)
	}
}
