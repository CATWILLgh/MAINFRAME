//go:build darwin || linux

package main

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const legacyCredentialTransferPlanSchemaVersion = 1

type catalogEnrichmentState string

const (
	catalogEnrichmentAvailable catalogEnrichmentState = "available"
	catalogEnrichmentBlocked   catalogEnrichmentState = "blocked"
)

type legacyCredentialTransferPlanResponse struct {
	SchemaVersion      int                                 `json:"schema_version"`
	Kind               string                              `json:"kind"`
	Scope              string                              `json:"scope"`
	ReleaseID          string                              `json:"release_id"`
	MigrationPerformed bool                                `json:"migration_performed"`
	ApplyAvailable     bool                                `json:"apply_available"`
	MigrationReadiness credentialmigration.Readiness       `json:"migration_readiness"`
	SourceAccounting   credentialmigration.AccountingState `json:"source_accounting"`
	ContentAccounting  credentialmigration.AccountingState `json:"content_accounting"`
	CatalogEnrichment  catalogEnrichmentState              `json:"catalog_enrichment"`
	Sources            []legacyPlanSourceResponse          `json:"sources"`
	Groups             []legacyPlanGroupResponse           `json:"groups"`
	Relationships      []legacyPlanRelationshipResponse    `json:"relationships"`
}

type legacyPlanSourceResponse struct {
	ComponentID        domain.ComponentID                  `json:"component_id"`
	ResourceID         string                              `json:"resource_id"`
	SourceRole         credentialmigration.SourceRole      `json:"source_role"`
	State              credentialmigration.IndexState      `json:"state"`
	UnsafeReason       credentialmigration.UnsafeReason    `json:"unsafe_reason,omitempty"`
	MigrationReadiness credentialmigration.Readiness       `json:"migration_readiness"`
	ContentAccounting  credentialmigration.AccountingState `json:"content_accounting"`
	Summary            legacyPlanSummaryResponse           `json:"summary"`
}

type legacyPlanSummaryResponse struct {
	TotalReferenceMentions     int `json:"total_reference_mentions"`
	ExtractedReferenceMentions int `json:"extracted_reference_mentions"`
	ExcludedReferenceMentions  int `json:"excluded_reference_mentions"`
	ExcludedExampleMentions    int `json:"excluded_example_mentions"`
	MalformedReferenceMentions int `json:"malformed_reference_mentions"`
	UnscopedReferenceMentions  int `json:"unscoped_reference_mentions"`
	UnmappedContentLines       int `json:"unmapped_content_lines"`
	InvalidHeadingLines        int `json:"invalid_heading_lines"`
	ExcludedContentLines       int `json:"excluded_content_lines"`
}

type legacyPlanGroupResponse struct {
	ComponentID          domain.ComponentID             `json:"component_id"`
	ResourceID           string                         `json:"resource_id"`
	SourceRole           credentialmigration.SourceRole `json:"source_role"`
	SectionPath          []string                       `json:"section_path"`
	UnmappedContentLines int                            `json:"unmapped_content_lines"`
	Proposals            []legacyPlanProposalResponse   `json:"proposals"`
}

type legacyPlanProposalResponse struct {
	ReferenceName    string                                     `json:"reference_name"`
	Occurrences      int                                        `json:"occurrences"`
	Compatibility    credentialmigration.ReferenceCompatibility `json:"compatibility"`
	SuggestedBackend string                                     `json:"suggested_backend,omitempty"`
	Decision         credentialmigration.ProposalDecision       `json:"decision"`
	UnresolvedFields []credentialmigration.TargetField          `json:"unresolved_fields"`
	ExistingUses     []credentialUseResponse                    `json:"existing_uses"`
}

type legacyPlanRelationshipResponse struct {
	Kind          credentialmigration.RelationshipKind `json:"kind"`
	ReferenceName string                               `json:"reference_name,omitempty"`
	Groups        []legacyPlanGroupIdentityResponse    `json:"groups"`
}

type legacyPlanGroupIdentityResponse struct {
	ComponentID domain.ComponentID `json:"component_id"`
	ResourceID  string             `json:"resource_id"`
	SectionPath []string           `json:"section_path"`
}

type legacyCatalogEnrichment struct {
	State catalogEnrichmentState
	Uses  map[string][]credentialUseResponse
}

func runLegacyCredentialTransferPlan(output io.Writer) error {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return err
	}
	plan, err := inspectLegacyCredentialTransferPlan(
		snapshot.release,
		snapshot.root,
		hostEnvironment(),
	)
	if err != nil {
		return err
	}
	enrichment := loadLegacyCatalogEnrichment(snapshot, plan)
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(
		publicLegacyCredentialTransferPlan(plan, enrichment),
	); err != nil {
		return fmt.Errorf("encode legacy credential transfer plan: %w", err)
	}
	return nil
}

func inspectLegacyCredentialTransferPlan(
	release releasecontract.Release,
	source string,
	environment hostlayout.Environment,
) (credentialmigration.LegacyTransferPlan, error) {
	layout, err := hostlayout.Resolve(environment, source)
	if err != nil {
		return credentialmigration.LegacyTransferPlan{}, fmt.Errorf(
			"resolve legacy credential locations: %w",
			err,
		)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return credentialmigration.LegacyTransferPlan{}, fmt.Errorf(
			"open legacy credential namespace: %w",
			err,
		)
	}
	return credentialmigration.InspectLegacyTransferPlan(release, namespace)
}

func loadLegacyCatalogEnrichment(
	snapshot readOnlyReleaseSnapshot,
	plan credentialmigration.LegacyTransferPlan,
) legacyCatalogEnrichment {
	definitions, err := credentialcatalog.ParseDefinitions(
		credentialcatalog.BundledDefinitionsJSON(),
		snapshot.release.MCPCatalog,
	)
	if err != nil {
		return legacyCatalogEnrichment{State: catalogEnrichmentBlocked}
	}
	instances, err := loadCredentialInstances(snapshot, definitions)
	if err != nil {
		return legacyCatalogEnrichment{State: catalogEnrichmentBlocked}
	}
	uses := make(map[string][]credentialUseResponse)
	for _, group := range plan.Groups {
		for _, proposal := range group.Proposals {
			if _, exists := uses[proposal.ReferenceName]; exists {
				continue
			}
			uses[proposal.ReferenceName] = publicCredentialUses(
				credentialcatalog.SecretReference{
					Backend: credentialcatalog.BackendSecretEnvironment,
					Name:    proposal.ReferenceName,
				},
				instances,
			).Uses
		}
	}
	return legacyCatalogEnrichment{
		State: catalogEnrichmentAvailable,
		Uses:  uses,
	}
}

func publicLegacyCredentialTransferPlan(
	plan credentialmigration.LegacyTransferPlan,
	enrichment legacyCatalogEnrichment,
) legacyCredentialTransferPlanResponse {
	return legacyCredentialTransferPlanResponse{
		SchemaVersion:      legacyCredentialTransferPlanSchemaVersion,
		Kind:               "mainframe-legacy-credential-transfer-plan",
		Scope:              "all-classified-legacy-sources",
		ReleaseID:          plan.ReleaseID,
		MigrationPerformed: false,
		ApplyAvailable:     false,
		MigrationReadiness: plan.MigrationReadiness,
		SourceAccounting:   plan.SourceAccounting,
		ContentAccounting:  plan.ContentAccounting,
		CatalogEnrichment:  enrichment.State,
		Sources:            publicLegacyPlanSources(plan.Sources),
		Groups:             publicLegacyPlanGroups(plan.Groups, enrichment),
		Relationships:      publicLegacyPlanRelationships(plan.Relationships),
	}
}

func publicLegacyPlanSources(
	sources []credentialmigration.LegacyPlanSource,
) []legacyPlanSourceResponse {
	result := make([]legacyPlanSourceResponse, len(sources))
	for index, source := range sources {
		result[index] = legacyPlanSourceResponse{
			ComponentID:        source.ComponentID,
			ResourceID:         source.ResourceID,
			SourceRole:         source.SourceRole,
			State:              source.State,
			UnsafeReason:       source.UnsafeReason,
			MigrationReadiness: source.MigrationReadiness,
			ContentAccounting:  source.ContentAccounting,
			Summary:            publicLegacyReferenceSummary(source.Summary),
		}
	}
	return result
}

func publicLegacyReferenceSummary(
	preview credentialmigration.LegacyReferencePreview,
) legacyPlanSummaryResponse {
	return legacyPlanSummaryResponse{
		TotalReferenceMentions:     preview.TotalReferenceMentions,
		ExtractedReferenceMentions: preview.ExtractedReferenceMentions,
		ExcludedReferenceMentions:  preview.ExcludedReferenceMentions,
		ExcludedExampleMentions:    preview.ExcludedExampleMentions,
		MalformedReferenceMentions: preview.MalformedReferenceMentions,
		UnscopedReferenceMentions:  preview.UnscopedReferenceMentions,
		UnmappedContentLines:       preview.UnmappedContentLines,
		InvalidHeadingLines:        preview.InvalidHeadingLines,
		ExcludedContentLines:       preview.ExcludedContentLines,
	}
}

func publicLegacyPlanGroups(
	groups []credentialmigration.LegacyPlanGroup,
	enrichment legacyCatalogEnrichment,
) []legacyPlanGroupResponse {
	result := make([]legacyPlanGroupResponse, len(groups))
	for index, group := range groups {
		proposals := make([]legacyPlanProposalResponse, len(group.Proposals))
		for proposalIndex, proposal := range group.Proposals {
			proposals[proposalIndex] = legacyPlanProposalResponse{
				ReferenceName:    proposal.ReferenceName,
				Occurrences:      proposal.Occurrences,
				Compatibility:    proposal.Compatibility,
				SuggestedBackend: proposal.SuggestedBackend,
				Decision:         proposal.Decision,
				UnresolvedFields: append(
					[]credentialmigration.TargetField(nil),
					proposal.UnresolvedFields...,
				),
				ExistingUses: append(
					[]credentialUseResponse(nil),
					enrichment.Uses[proposal.ReferenceName]...,
				),
			}
		}
		result[index] = legacyPlanGroupResponse{
			ComponentID:          group.ComponentID,
			ResourceID:           group.ResourceID,
			SourceRole:           group.SourceRole,
			SectionPath:          append([]string(nil), group.SectionPath...),
			UnmappedContentLines: group.UnmappedContentLines,
			Proposals:            proposals,
		}
	}
	return result
}

func publicLegacyPlanRelationships(
	relationships []credentialmigration.LegacyPlanRelationship,
) []legacyPlanRelationshipResponse {
	result := make([]legacyPlanRelationshipResponse, len(relationships))
	for index, relationship := range relationships {
		groups := make(
			[]legacyPlanGroupIdentityResponse,
			len(relationship.Groups),
		)
		for groupIndex, group := range relationship.Groups {
			groups[groupIndex] = legacyPlanGroupIdentityResponse{
				ComponentID: group.ComponentID,
				ResourceID:  group.ResourceID,
				SectionPath: append([]string(nil), group.SectionPath...),
			}
		}
		result[index] = legacyPlanRelationshipResponse{
			Kind:          relationship.Kind,
			ReferenceName: relationship.ReferenceName,
			Groups:        groups,
		}
	}
	return result
}
