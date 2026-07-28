//go:build darwin || linux

package main

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const legacyCredentialReferencePreviewSchemaVersion = 1

type legacyCredentialReferencePreviewResponse struct {
	SchemaVersion      int                             `json:"schema_version"`
	Kind               string                          `json:"kind"`
	Scope              string                          `json:"scope"`
	Coverage           string                          `json:"coverage"`
	ReleaseID          string                          `json:"release_id"`
	MigrationPerformed bool                            `json:"migration_performed"`
	ApplyAvailable     bool                            `json:"apply_available"`
	RequiresReview     bool                            `json:"requires_review"`
	MigrationReadiness credentialmigration.Readiness   `json:"migration_readiness"`
	Sources            []legacyReferenceSourceResponse `json:"sources"`
	PendingSources     []legacyReferenceSourceResponse `json:"pending_sources"`
	Summary            legacyReferenceSummaryResponse  `json:"summary"`
	Groups             []legacyReferenceGroupResponse  `json:"groups"`
}

type legacyReferenceSourceResponse struct {
	ComponentID        domain.ComponentID             `json:"component_id"`
	ResourceID         string                         `json:"resource_id"`
	SourceRole         credentialmigration.SourceRole `json:"source_role"`
	State              credentialmigration.IndexState `json:"state"`
	MigrationReadiness credentialmigration.Readiness  `json:"migration_readiness"`
	Extraction         string                         `json:"reference_extraction"`
}

type legacyReferenceSummaryResponse struct {
	TotalReferenceMentions     int `json:"total_reference_mentions"`
	ExtractedReferenceMentions int `json:"extracted_reference_mentions"`
	ExcludedReferenceMentions  int `json:"excluded_reference_mentions"`
	ExcludedExampleMentions    int `json:"excluded_example_mentions"`
	MalformedReferenceMentions int `json:"malformed_reference_mentions"`
	UnscopedReferenceMentions  int `json:"unscoped_reference_mentions"`
	UnmappedContentLines       int `json:"unmapped_content_lines"`
}

type legacyReferenceGroupResponse struct {
	SectionPath  []string                          `json:"section_path"`
	MappingState string                            `json:"mapping_status"`
	References   []legacyCredentialReferenceRecord `json:"references"`
}

type legacyCredentialReferenceRecord struct {
	Name          string                                     `json:"name"`
	Occurrences   int                                        `json:"occurrences"`
	Compatibility credentialmigration.ReferenceCompatibility `json:"compatibility"`
}

func runLegacyCredentialReferencePreview(output io.Writer) error {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return err
	}
	inventory, err := inspectLegacyCredentialReferencePreview(
		snapshot.release,
		snapshot.root,
		hostEnvironment(),
	)
	if err != nil {
		return err
	}
	return writeLegacyCredentialReferencePreview(output, inventory)
}

func inspectLegacyCredentialReferencePreview(
	release releasecontract.Release,
	source string,
	environment hostlayout.Environment,
) (credentialmigration.LegacyReferenceInventory, error) {
	layout, err := hostlayout.Resolve(environment, source)
	if err != nil {
		return credentialmigration.LegacyReferenceInventory{}, fmt.Errorf(
			"resolve legacy credential locations: %w",
			err,
		)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return credentialmigration.LegacyReferenceInventory{}, fmt.Errorf(
			"open legacy credential namespace: %w",
			err,
		)
	}
	return credentialmigration.InspectLegacyReferencePreview(
		release,
		namespace,
	)
}

func writeLegacyCredentialReferencePreview(
	output io.Writer,
	inventory credentialmigration.LegacyReferenceInventory,
) error {
	response := publicLegacyCredentialReferencePreview(inventory)
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(response); err != nil {
		return fmt.Errorf("encode legacy credential reference preview: %w", err)
	}
	return nil
}

func publicLegacyCredentialReferencePreview(
	inventory credentialmigration.LegacyReferenceInventory,
) legacyCredentialReferencePreviewResponse {
	references := inventory.References
	return legacyCredentialReferencePreviewResponse{
		SchemaVersion:      legacyCredentialReferencePreviewSchemaVersion,
		Kind:               "mainframe-legacy-credential-reference-preview",
		Scope:              "shared-original-reference-discovery",
		Coverage:           "partial",
		ReleaseID:          inventory.ReleaseID,
		MigrationPerformed: false,
		ApplyAvailable:     false,
		RequiresReview: inventory.MigrationReadiness !=
			credentialmigration.ReadinessNoTransferRequired,
		MigrationReadiness: inventory.MigrationReadiness,
		Sources:            publicLegacyReferenceSources(inventory.Indexes),
		PendingSources:     publicPendingLegacyReferenceSources(inventory.Indexes),
		Summary: legacyReferenceSummaryResponse{
			TotalReferenceMentions:     references.TotalReferenceMentions,
			ExtractedReferenceMentions: references.ExtractedReferenceMentions,
			ExcludedReferenceMentions:  references.ExcludedReferenceMentions,
			ExcludedExampleMentions:    references.ExcludedExampleMentions,
			MalformedReferenceMentions: references.MalformedReferenceMentions,
			UnscopedReferenceMentions:  references.UnscopedReferenceMentions,
			UnmappedContentLines:       references.UnmappedContentLines,
		},
		Groups: publicLegacyReferenceGroups(references.Groups),
	}
}

func publicPendingLegacyReferenceSources(
	indexes []credentialmigration.LegacyIndex,
) []legacyReferenceSourceResponse {
	result := make([]legacyReferenceSourceResponse, 0)
	for _, source := range publicLegacyReferenceSources(indexes) {
		if source.SourceRole == credentialmigration.SourceRoleAdapterCopy &&
			(source.Extraction == "pending" || source.Extraction == "blocked") {
			result = append(result, source)
		}
	}
	return result
}

func publicLegacyReferenceSources(
	indexes []credentialmigration.LegacyIndex,
) []legacyReferenceSourceResponse {
	result := make([]legacyReferenceSourceResponse, len(indexes))
	for index, source := range indexes {
		result[index] = legacyReferenceSourceResponse{
			ComponentID:        source.ComponentID,
			ResourceID:         source.ResourceID,
			SourceRole:         source.SourceRole,
			State:              source.State,
			MigrationReadiness: source.MigrationReadiness,
			Extraction:         legacyReferenceExtraction(source),
		}
	}
	return result
}

func legacyReferenceExtraction(source credentialmigration.LegacyIndex) string {
	switch {
	case source.SourceRole == credentialmigration.SourceRoleAdapterCopy &&
		source.MigrationReadiness ==
			credentialmigration.ReadinessManualTransferRequired:
		return "pending"
	case source.MigrationReadiness == credentialmigration.ReadinessBlocked:
		return "blocked"
	case source.MigrationReadiness ==
		credentialmigration.ReadinessNoTransferRequired:
		return "not_needed"
	default:
		return "attempted"
	}
}

func publicLegacyReferenceGroups(
	groups []credentialmigration.LegacyReferenceGroup,
) []legacyReferenceGroupResponse {
	result := make([]legacyReferenceGroupResponse, len(groups))
	for index, group := range groups {
		result[index] = legacyReferenceGroupResponse{
			SectionPath:  append([]string(nil), group.SectionPath...),
			MappingState: "manual_service_mapping_required",
			References:   publicLegacyReferences(group.References),
		}
	}
	return result
}

func publicLegacyReferences(
	references []credentialmigration.LegacyReference,
) []legacyCredentialReferenceRecord {
	result := make([]legacyCredentialReferenceRecord, len(references))
	for index, reference := range references {
		result[index] = legacyCredentialReferenceRecord{
			Name: reference.Name, Occurrences: reference.Occurrences,
			Compatibility: reference.Compatibility,
		}
	}
	return result
}
