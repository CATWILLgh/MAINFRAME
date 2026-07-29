//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestLegacyCredentialTransferReviewDoesNotExposeSetupErrors(t *testing.T) {
	privatePath := filepath.Join(t.TempDir(), "legacy-private-canary")
	t.Setenv(releaseRootEnvironment, privatePath)
	var stdout, stderr bytes.Buffer
	input := strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-legacy-credential-transfer-draft",
		"release_id":"release-a",
		"new_instances":[],
		"choices":[]
	}`)

	exitCode := run(
		[]string{"credentials", "legacy-review"},
		input,
		&stdout,
		&stderr,
	)
	if exitCode == 0 ||
		stdout.Len() != 0 ||
		!strings.Contains(stderr.String(), "could not be reviewed safely") ||
		strings.Contains(stderr.String(), privatePath) {
		t.Fatalf(
			"legacy review exit/stdout/stderr = %d/%q/%q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}

func TestReviewLegacyCredentialTransferDraftReturnsReadOnlyAfterImage(
	t *testing.T,
) {
	definitions := legacyReviewDefinitions(t)
	current, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{{
			ID: "dokploy-existing", ServiceID: "dokploy",
			Name: "Existing", Purpose: "Existing deployment",
			Credentials: []credentialcatalog.CredentialBinding{{
				RoleID: "api-key",
				Secret: credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment,
					Name:    "SHARED_KEY",
				},
			}},
		}},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	plan := legacyReviewPlanFixture()
	request := legacyTransferReviewRequest{
		SchemaVersion: legacyTransferReviewSchemaVersion,
		Kind:          legacyTransferReviewRequestKind,
		ReleaseID:     plan.ReleaseID,
		NewInstances:  []credentialInstance{},
		Choices: []legacyTransferChoiceRequest{{
			Proposal: legacyProposalIdentityRequest{
				ComponentID:   domain.ComponentClaudeCode,
				ResourceID:    "claude-code.credentials-index",
				SourceRole:    credentialmigration.SourceRoleSharedOriginal,
				SectionPath:   []string{"Catalog", "Home"},
				ReferenceName: "SHARED_KEY",
			},
			ExpectedOccurrences: 2,
			Action:              credentialmigration.TransferChoiceTransfer,
			Target: legacyTransferTargetRequest{
				InstanceID: "dokploy-existing",
				RoleID:     "api-key",
			},
		}},
	}

	response, err := reviewLegacyCredentialTransferDraft(
		plan,
		current,
		definitions,
		request,
	)
	if err != nil {
		t.Fatalf("reviewLegacyCredentialTransferDraft() error = %v", err)
	}
	if response.MigrationPerformed || response.ApplyAvailable ||
		response.ReferenceChoicesComplete ||
		!response.ManualContentReviewRequired ||
		response.RetirementReady ||
		len(response.After.Instances) != 1 ||
		response.Summary.Transferred != 1 ||
		response.Summary.Pending != 1 {
		t.Fatalf("response = %#v", response)
	}
	payload, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("marshal response: %v", err)
	}
	for _, denied := range []string{
		"apply_request",
		"expected_review",
		"digest",
		"source_content",
		"raw_line",
		"description",
		"location",
	} {
		if strings.Contains(string(payload), `"`+denied+`"`) {
			t.Fatalf("response contains denied field %q: %s", denied, payload)
		}
	}
}

func TestDecodeLegacyTransferReviewRejectsUnknownAndIncompleteInput(
	t *testing.T,
) {
	valid := `{
		"schema_version":1,
		"kind":"mainframe-legacy-credential-transfer-draft",
		"release_id":"release-a",
		"new_instances":[],
		"choices":[]
	}`
	if _, err := decodeLegacyTransferReview(strings.NewReader(valid)); err != nil {
		t.Fatalf("decodeLegacyTransferReview() error = %v", err)
	}
	for name, payload := range map[string]string{
		"unknown field": strings.Replace(
			valid,
			`"choices":[]`,
			`"choices":[],"private":"canary"`,
			1,
		),
		"missing choices": `{
			"schema_version":1,
			"kind":"mainframe-legacy-credential-transfer-draft",
			"release_id":"release-a",
			"new_instances":[]
		}`,
		"missing new instances": `{
			"schema_version":1,
			"kind":"mainframe-legacy-credential-transfer-draft",
			"release_id":"release-a",
			"choices":[]
		}`,
		"wrong kind": strings.Replace(
			valid,
			"mainframe-legacy-credential-transfer-draft",
			"other",
			1,
		),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeLegacyTransferReview(
				strings.NewReader(payload),
			); err == nil {
				t.Fatal("decodeLegacyTransferReview() error = nil")
			}
		})
	}
}

func legacyReviewPlanFixture() credentialmigration.LegacyTransferPlan {
	return credentialmigration.LegacyTransferPlan{
		ReleaseID:          "release-a",
		MigrationReadiness: credentialmigration.ReadinessManualTransferRequired,
		SourceAccounting:   credentialmigration.AccountingComplete,
		ContentAccounting:  credentialmigration.AccountingPartial,
		Groups: []credentialmigration.LegacyPlanGroup{
			{
				ComponentID: domain.ComponentClaudeCode,
				ResourceID:  "claude-code.credentials-index",
				SourceRole:  credentialmigration.SourceRoleSharedOriginal,
				SectionPath: []string{"Catalog", "Home"},
				Proposals: []credentialmigration.LegacyCredentialProposal{{
					ReferenceName: "SHARED_KEY",
					Occurrences:   2,
					Compatibility: credentialmigration.ReferenceCatalogCompatible,
				}},
			},
			{
				ComponentID: domain.ComponentCodex,
				ResourceID:  "codex.credentials-index",
				SourceRole:  credentialmigration.SourceRoleAdapterCopy,
				SectionPath: []string{"Catalog", "Work"},
				Proposals: []credentialmigration.LegacyCredentialProposal{{
					ReferenceName: "SHARED_KEY",
					Occurrences:   1,
					Compatibility: credentialmigration.ReferenceCatalogCompatible,
				}},
			},
		},
	}
}

func legacyReviewDefinitions(t *testing.T) credentialcatalog.Definitions {
	t.Helper()
	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-definitions",
		"services":[{
			"id":"dokploy",
			"name":"Dokploy",
			"summary":"Deployment control plane.",
			"source":{"kind":"standalone"},
			"credential_roles":[{
				"id":"api-key",
				"name":"API key",
				"purpose":"Call the API.",
				"acquisition":"Create it."
			}]
		}]
	}`)
	definitions, err := credentialcatalog.ParseDefinitions(
		payload,
		mcpcatalog.Catalog{},
	)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}
	return definitions
}
