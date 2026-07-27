package main

import (
	"errors"
	"fmt"
	"io"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

const (
	draftProtocolVersion    = 1
	draftRequestKind        = "mainframe-draft"
	draftReviewResponseKind = "mainframe-draft-review"
	draftApplyResponseKind  = "mainframe-draft-apply-result"
	draftStateSemantics     = "complete-desired-state"
	draftDiagnosticsPolicy  = "preserve-retained-adapters"
)

type draftReviewRequest struct {
	SchemaVersion int               `json:"schema_version"`
	Kind          string            `json:"kind"`
	Desired       draftDesiredState `json:"desired"`
}

type draftDesiredState struct {
	Adapters          []domain.ComponentID `json:"adapters"`
	MCP               []draftMCPSelection  `json:"mcp"`
	DiagnosticsPolicy string               `json:"diagnostics_policy"`
}

type draftMCPSelection struct {
	ServerID             mcpcatalog.ServerID          `json:"server_id"`
	ProfileID            mcpcatalog.ProfileID         `json:"profile_id"`
	Adapters             []domain.ComponentID         `json:"adapters"`
	CredentialInstanceID credentialcatalog.InstanceID `json:"credential_instance_id,omitempty"`
}

type draftReviewResponse struct {
	SchemaVersion  int                    `json:"schema_version"`
	Kind           string                 `json:"kind"`
	StateSemantics string                 `json:"state_semantics"`
	Desired        draftDesiredState      `json:"desired"`
	Preview        draftSemanticPreview   `json:"preview"`
	Onboarding     draftOnboardingPreview `json:"onboarding"`
	Apply          draftApplyAvailability `json:"apply"`
}

type draftSemanticPreview struct {
	Filesystem    draftFilesystemPreview    `json:"filesystem"`
	Configuration draftConfigurationPreview `json:"configuration"`
	MCP           draftMCPPreview           `json:"mcp"`
	Diagnostics   draftDiagnosticsPreview   `json:"diagnostics"`
}

type draftFilesystemPreview struct {
	Operations []draftFilesystemOperation `json:"operations"`
}

type draftFilesystemOperation struct {
	ComponentID domain.ComponentID   `json:"component_id"`
	UnitID      string               `json:"unit_id,omitempty"`
	Kind        domain.OperationKind `json:"kind"`
}

type draftConfigurationPreview struct {
	Changes       []draftConfigurationChange       `json:"changes"`
	Issues        []draftConfigurationIssue        `json:"issues"`
	ManualActions []draftConfigurationManualAction `json:"manual_actions"`
	Notices       []draftConfigurationNotice       `json:"notices"`
}

type draftConfigurationChange struct {
	ResourceID  string                   `json:"resource_id"`
	ComponentID domain.ComponentID       `json:"component_id"`
	UnitID      string                   `json:"unit_id,omitempty"`
	Kind        configuration.ChangeKind `json:"kind"`
}

type draftConfigurationIssue struct {
	ResourceID  string                  `json:"resource_id"`
	ComponentID domain.ComponentID      `json:"component_id"`
	UnitID      string                  `json:"unit_id,omitempty"`
	Kind        configuration.IssueKind `json:"kind"`
	Reason      configuration.Reason    `json:"reason"`
}

type draftConfigurationManualAction struct {
	ResourceID  string                         `json:"resource_id"`
	ComponentID domain.ComponentID             `json:"component_id"`
	Kind        configuration.ManualActionKind `json:"kind"`
	Reason      configuration.Reason           `json:"reason"`
}

type draftConfigurationNotice struct {
	ResourceID  string               `json:"resource_id"`
	ComponentID domain.ComponentID   `json:"component_id"`
	Reason      configuration.Reason `json:"reason"`
}

type draftMCPPreview struct {
	Intents    []draftMCPIntent    `json:"intents"`
	Migrations []draftMCPMigration `json:"migrations"`
	Blocking   bool                `json:"blocking"`
}

type draftMCPIntent struct {
	ComponentID domain.ComponentID          `json:"component_id"`
	ServerID    mcpcatalog.ServerID         `json:"server_id"`
	ProfileID   mcpcatalog.ProfileID        `json:"profile_id"`
	Kind        mcpconfiguration.IntentKind `json:"kind"`
	Reason      string                      `json:"reason,omitempty"`
}

type draftMCPMigration struct {
	ComponentID       domain.ComponentID              `json:"component_id"`
	State             mcpconfiguration.MigrationState `json:"state"`
	Reason            string                          `json:"reason,omitempty"`
	RequiresMigration bool                            `json:"requires_migration"`
	Conflict          bool                            `json:"conflict"`
}

type draftDiagnosticsPreview struct {
	Intents    []draftDiagnosticsIntent `json:"intents"`
	Executable bool                     `json:"executable"`
}

type draftDiagnosticsIntent struct {
	ComponentID domain.ComponentID `json:"component_id"`
	Events      bool               `json:"events"`
	Feedback    bool               `json:"feedback"`
}

type draftOnboardingPreview struct {
	Connections []draftOnboardingConnection `json:"connections"`
	Executable  bool                        `json:"executable"`
}

type draftOnboardingConnection struct {
	ServerID             mcpcatalog.ServerID           `json:"server_id"`
	ServerName           string                        `json:"server_name"`
	ProfileID            mcpcatalog.ProfileID          `json:"profile_id"`
	ProfileName          string                        `json:"profile_name"`
	Transport            mcpcatalog.Transport          `json:"transport"`
	Authentication       mcpcatalog.AuthenticationKind `json:"authentication"`
	Adapters             []domain.ComponentID          `json:"adapters"`
	CredentialInstanceID credentialcatalog.InstanceID  `json:"credential_instance_id,omitempty"`
}

type draftApplyAvailability struct {
	CommandAvailable bool   `json:"command_available"`
	Confirmation     string `json:"confirmation,omitempty"`
}

type draftApplyResponse struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Warnings      []string `json:"warnings"`
}

func decodeDraftReviewRequest(input io.Reader) (draftReviewRequest, error) {
	request, err := decodeStrictJSON[draftReviewRequest](input)
	if err != nil {
		return draftReviewRequest{}, err
	}
	if request.SchemaVersion != draftProtocolVersion {
		return draftReviewRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != draftRequestKind {
		return draftReviewRequest{}, errors.New("request kind is unsupported")
	}
	if request.Desired.Adapters == nil || request.Desired.MCP == nil {
		return draftReviewRequest{}, errors.New(
			"desired adapters and mcp must both be arrays",
		)
	}
	if request.Desired.DiagnosticsPolicy != draftDiagnosticsPolicy {
		return draftReviewRequest{}, errors.New(
			"diagnostics_policy must preserve retained adapters",
		)
	}
	return request, nil
}

func normalizeDraftReviewRequest(
	catalog mcpcatalog.Catalog,
	request draftReviewRequest,
) (draftDesiredState, application.Request, mcpcatalog.OnboardingPreview, error) {
	selections := make([]mcpcatalog.Selection, len(request.Desired.MCP))
	for index, selection := range request.Desired.MCP {
		selections[index] = mcpcatalog.Selection{
			ServerID: selection.ServerID, ProfileID: selection.ProfileID,
			Adapters: append([]domain.ComponentID(nil), selection.Adapters...),
		}
	}
	onboarding, err := catalog.Preview(request.Desired.Adapters, selections)
	if err != nil {
		return draftDesiredState{}, application.Request{},
			mcpcatalog.OnboardingPreview{}, err
	}
	normalized := normalizedDraftDesired(request.Desired, onboarding)
	if err := validateDraftCredentialSelections(normalized, onboarding); err != nil {
		return draftDesiredState{}, application.Request{},
			mcpcatalog.OnboardingPreview{}, err
	}
	internal := application.Request{
		Components: append([]domain.ComponentID(nil), normalized.Adapters...),
	}
	for _, selection := range normalized.MCP {
		internal.MCPSelections = append(
			internal.MCPSelections,
			mcpcatalog.Selection{
				ServerID: selection.ServerID, ProfileID: selection.ProfileID,
				Adapters: append([]domain.ComponentID(nil), selection.Adapters...),
			},
		)
		if selection.CredentialInstanceID == "" {
			continue
		}
		if strings.TrimSpace(string(selection.CredentialInstanceID)) !=
			string(selection.CredentialInstanceID) {
			return draftDesiredState{}, application.Request{},
				mcpcatalog.OnboardingPreview{},
				errors.New(
					"credential-bound MCP selection requires a valid instance id",
				)
		}
		for _, adapter := range selection.Adapters {
			internal.MCPCredentials = append(internal.MCPCredentials,
				application.MCPCredentialBinding{
					ComponentID: adapter,
					ServerID:    selection.ServerID, ProfileID: selection.ProfileID,
					InstanceID: selection.CredentialInstanceID,
				},
			)
		}
	}
	return normalized, internal, onboarding, nil
}

func validateDraftCredentialSelections(
	desired draftDesiredState,
	onboarding mcpcatalog.OnboardingPreview,
) error {
	credentials := make(map[mcpcatalog.ServerID]credentialcatalog.InstanceID)
	for _, selection := range desired.MCP {
		credentials[selection.ServerID] = selection.CredentialInstanceID
	}
	for _, connection := range onboarding.Connections {
		instanceID := credentials[connection.ServerID]
		requiresCredential :=
			connection.Profile.Authentication.Kind == mcpcatalog.AuthenticationAPIKey ||
				connection.Profile.ServiceCredential != nil
		if requiresCredential != (instanceID != "") {
			return errors.New(
				"selected MCP profile and credential instance do not match",
			)
		}
		if instanceID == "" {
			continue
		}
		for _, adapter := range connection.Adapters {
			if !application.SupportsMCPCredentialBinding(adapter) {
				return errors.New(
					"credential-bound MCP profile is unavailable for a selected adapter",
				)
			}
		}
	}
	return nil
}

func normalizedDraftDesired(
	desired draftDesiredState,
	onboarding mcpcatalog.OnboardingPreview,
) draftDesiredState {
	adapters := make([]domain.ComponentID, len(desired.Adapters))
	copy(adapters, desired.Adapters)
	sort.Slice(adapters, func(left, right int) bool {
		return adapters[left] < adapters[right]
	})
	credentials := make(map[mcpcatalog.ServerID]credentialcatalog.InstanceID)
	for _, selection := range desired.MCP {
		credentials[selection.ServerID] = selection.CredentialInstanceID
	}
	mcp := make([]draftMCPSelection, len(onboarding.Connections))
	for index, connection := range onboarding.Connections {
		mcp[index] = draftMCPSelection{
			ServerID: connection.ServerID, ProfileID: connection.Profile.ID,
			Adapters:             append([]domain.ComponentID(nil), connection.Adapters...),
			CredentialInstanceID: credentials[connection.ServerID],
		}
	}
	return draftDesiredState{
		Adapters: adapters, MCP: mcp,
		DiagnosticsPolicy: desired.DiagnosticsPolicy,
	}
}
