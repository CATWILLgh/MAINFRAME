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

const legacyCredentialInventorySchemaVersion = 3

type runtimeLegacyIndexInspector struct {
	release     releasecontract.Release
	source      string
	environment hostlayout.Environment
}

type legacyCredentialInventoryResponse struct {
	SchemaVersion      int                             `json:"schema_version"`
	Kind               string                          `json:"kind"`
	Scope              string                          `json:"scope"`
	ReleaseID          string                          `json:"release_id"`
	ReleaseIndexSHA256 string                          `json:"release_index_sha256"`
	MigrationPerformed bool                            `json:"migration_performed"`
	MigrationReadiness credentialmigration.Readiness   `json:"migration_readiness"`
	Indexes            []legacyCredentialIndexResponse `json:"indexes"`
}

type legacyCredentialIndexResponse struct {
	ComponentID            domain.ComponentID               `json:"component_id"`
	ResourceID             string                           `json:"resource_id"`
	Location               domain.Location                  `json:"location"`
	SourceRole             credentialmigration.SourceRole   `json:"source_role"`
	State                  credentialmigration.IndexState   `json:"state"`
	SizeBytes              *int                             `json:"size_bytes,omitempty"`
	MatchesCurrentTemplate *bool                            `json:"matches_current_release_template,omitempty"`
	UnsafeReason           credentialmigration.UnsafeReason `json:"unsafe_reason,omitempty"`
	MigrationReadiness     credentialmigration.Readiness    `json:"migration_readiness"`
}

func (inspector runtimeLegacyIndexInspector) Inspect() (
	[]credentialmigration.LegacyIndex,
	error,
) {
	inventory, err := inspectLegacyCredentialIndexes(
		inspector.release,
		inspector.source,
		inspector.environment,
	)
	if err != nil {
		return nil, err
	}
	return append(
		[]credentialmigration.LegacyIndex(nil),
		inventory.Indexes...,
	), nil
}

func (inspector runtimeLegacyIndexInspector) Preview() (
	credentialmigration.LegacyReferenceInventory,
	error,
) {
	return inspectLegacyCredentialReferencePreview(
		inspector.release,
		inspector.source,
		inspector.environment,
	)
}

func (inspector runtimeLegacyIndexInspector) Plan() (
	credentialmigration.LegacyTransferPlan,
	error,
) {
	return inspectLegacyCredentialTransferPlan(
		inspector.release,
		inspector.source,
		inspector.environment,
	)
}

func runLegacyCredentialInventory(output io.Writer) error {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return err
	}
	inventory, err := inspectLegacyCredentialIndexes(
		snapshot.release,
		snapshot.root,
		hostEnvironment(),
	)
	if err != nil {
		return err
	}
	return writeLegacyCredentialInventory(output, inventory)
}

func inspectLegacyCredentialIndexes(
	release releasecontract.Release,
	source string,
	environment hostlayout.Environment,
) (credentialmigration.Inventory, error) {
	layout, err := hostlayout.Resolve(environment, source)
	if err != nil {
		return credentialmigration.Inventory{}, fmt.Errorf(
			"resolve legacy credential locations: %w",
			err,
		)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return credentialmigration.Inventory{}, fmt.Errorf(
			"open legacy credential namespace: %w",
			err,
		)
	}
	inventory, err := credentialmigration.InspectLegacyIndexes(
		release,
		namespace,
	)
	if err != nil {
		return credentialmigration.Inventory{}, err
	}
	return inventory, nil
}

func writeLegacyCredentialInventory(
	output io.Writer,
	inventory credentialmigration.Inventory,
) error {
	response := publicLegacyCredentialInventory(inventory)
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(response); err != nil {
		return fmt.Errorf("encode legacy credential inventory: %w", err)
	}
	return nil
}

func publicLegacyCredentialInventory(
	inventory credentialmigration.Inventory,
) legacyCredentialInventoryResponse {
	indexes := make(
		[]legacyCredentialIndexResponse,
		len(inventory.Indexes),
	)
	for index, item := range inventory.Indexes {
		indexes[index] = publicLegacyCredentialIndex(item)
	}
	return legacyCredentialInventoryResponse{
		SchemaVersion:      legacyCredentialInventorySchemaVersion,
		Kind:               "mainframe-legacy-credential-index-inventory",
		Scope:              "historical-credential-locations",
		ReleaseID:          inventory.ReleaseID,
		ReleaseIndexSHA256: inventory.ReleaseIndexSHA256,
		MigrationPerformed: false,
		MigrationReadiness: inventory.MigrationReadiness,
		Indexes:            indexes,
	}
}

func publicLegacyCredentialIndex(
	index credentialmigration.LegacyIndex,
) legacyCredentialIndexResponse {
	response := legacyCredentialIndexResponse{
		ComponentID:        index.ComponentID,
		ResourceID:         index.ResourceID,
		Location:           index.Location,
		SourceRole:         index.SourceRole,
		State:              index.State,
		UnsafeReason:       index.UnsafeReason,
		MigrationReadiness: index.MigrationReadiness,
	}
	if index.State == credentialmigration.IndexPresent {
		size := index.SizeBytes
		matches := index.MatchesCurrentTemplate
		response.SizeBytes = &size
		response.MatchesCurrentTemplate = &matches
	}
	return response
}
