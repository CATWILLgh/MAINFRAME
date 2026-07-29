//go:build darwin || linux

package main

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPublicLegacyCredentialTransferPlanIsReadOnlyAndValueFree(t *testing.T) {
	plan := credentialmigration.LegacyTransferPlan{
		ReleaseID:          "release-a",
		MigrationReadiness: credentialmigration.ReadinessManualTransferRequired,
		SourceAccounting:   credentialmigration.AccountingComplete,
		ContentAccounting:  credentialmigration.AccountingPartial,
		Sources: []credentialmigration.LegacyPlanSource{{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SourceRole:  credentialmigration.SourceRoleSharedOriginal,
			State:       credentialmigration.IndexPresent,
			MigrationReadiness: credentialmigration.
				ReadinessManualTransferRequired,
			ContentAccounting: credentialmigration.AccountingPartial,
			Summary: credentialmigration.LegacyReferencePreview{
				ExtractedReferenceMentions: 1,
				UnmappedContentLines:       1,
			},
		}},
		Groups: []credentialmigration.LegacyPlanGroup{{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SourceRole:  credentialmigration.SourceRoleSharedOriginal,
			SectionPath: []string{"Catalog", "Home"},
			Proposals: []credentialmigration.LegacyCredentialProposal{{
				ReferenceName:    "SAFE_KEY",
				Occurrences:      1,
				Compatibility:    credentialmigration.ReferenceCatalogCompatible,
				SuggestedBackend: "secret-env",
				Decision:         credentialmigration.DecisionNeedsReview,
				UnresolvedFields: []credentialmigration.TargetField{
					credentialmigration.TargetFieldServiceID,
				},
			}},
		}},
	}
	enrichment := legacyCatalogEnrichment{
		State: catalogEnrichmentAvailable,
		Uses: map[string][]credentialUseResponse{
			"SAFE_KEY": {{
				InstanceID:   "context7-home",
				ServiceID:    "context7",
				InstanceName: "Home",
				RoleID:       "api-key",
			}},
		},
	}

	response := publicLegacyCredentialTransferPlan(plan, enrichment)
	if response.MigrationPerformed || response.ApplyAvailable {
		t.Fatalf("write flags = %#v", response)
	}
	if response.CatalogEnrichment != catalogEnrichmentAvailable ||
		len(response.Groups) != 1 ||
		len(response.Groups[0].Proposals[0].ExistingUses) != 1 {
		t.Fatalf("response = %#v", response)
	}
	payload, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("marshal response: %v", err)
	}
	for _, denied := range []string{
		"apply_request",
		"expected_review",
		"release_index_sha256",
		"location",
		"size_bytes",
		"raw_line",
		"description",
		"source_content",
		"error",
		"digest",
		"after",
	} {
		if strings.Contains(string(payload), `"`+denied+`"`) {
			t.Fatalf("response contains denied field %q: %s", denied, payload)
		}
	}
}

func TestBlockedCatalogEnrichmentDoesNotHideLegacyPlan(t *testing.T) {
	response := publicLegacyCredentialTransferPlan(
		credentialmigration.LegacyTransferPlan{
			ReleaseID:        "release-a",
			SourceAccounting: credentialmigration.AccountingComplete,
			Groups: []credentialmigration.LegacyPlanGroup{{
				ResourceID: "claude-code.credentials-index",
			}},
		},
		legacyCatalogEnrichment{State: catalogEnrichmentBlocked},
	)
	if response.CatalogEnrichment != catalogEnrichmentBlocked ||
		len(response.Groups) != 1 {
		t.Fatalf("response = %#v", response)
	}
}
