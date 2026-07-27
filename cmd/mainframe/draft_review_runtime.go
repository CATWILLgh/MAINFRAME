package main

import (
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func reviewDraft(request draftReviewRequest) (draftReviewResponse, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return draftReviewResponse{}, err
	}
	normalized, internal, onboarding, err := normalizeDraftReviewRequest(
		snapshot.release.MCPCatalog,
		request,
	)
	if err != nil {
		return draftReviewResponse{}, fmt.Errorf("validate desired state: %w", err)
	}
	cwd, err := os.Getwd()
	if err != nil {
		return draftReviewResponse{}, fmt.Errorf("resolve working directory: %w", err)
	}
	builder := newMachineDraftSnapshotBuilder(snapshot.root, cwd)
	identity := releaseIdentity(snapshot.release)
	builder.expectedRelease = &identity
	reviewer, err := application.NewReviewer(builder)
	if err != nil {
		return draftReviewResponse{}, fmt.Errorf("build read-only reviewer: %w", err)
	}
	return reviewDraftWithReviewer(
		reviewer,
		internal,
		normalized,
		onboarding,
		snapshot.root,
		cwd,
	)
}

func reviewDraftWithReviewer(
	reviewer application.Reviewer,
	internal application.Request,
	normalized draftDesiredState,
	onboarding mcpcatalog.OnboardingPreview,
	releaseRoot string,
	cwd string,
) (draftReviewResponse, error) {
	reviewed, err := reviewer.Review(internal)
	if err != nil {
		semantic, previewErr := reviewer.Preview(internal)
		if previewErr != nil {
			return draftReviewResponse{}, err
		}
		if !draftReviewOnlyPlan(semantic) {
			return draftReviewResponse{}, err
		}
		return publicDraftReview(
			normalized,
			semantic,
			onboarding,
			false,
			"",
		), nil
	}
	confirmation := ""
	if reviewed.Applicable() {
		scope, err := buildDraftCommitmentScope(releaseRoot, cwd)
		if err != nil {
			return draftReviewResponse{}, err
		}
		confirmation, err = draftReviewCommitment(
			normalized,
			reviewed.Executable(),
			scope,
		)
		if err != nil {
			return draftReviewResponse{}, err
		}
	}
	return publicDraftReview(
		normalized,
		reviewed.Semantic(),
		onboarding,
		reviewed.Applicable(),
		confirmation,
	), nil
}

func draftReviewOnlyPlan(preview lifecycle.Preview) bool {
	return len(preview.Configuration.Issues) > 0 ||
		len(preview.Configuration.ManualActions) > 0 ||
		preview.MCP.Blocking ||
		!preview.Diagnostics.Executable
}

func buildDraftCommitmentScope(
	releaseRoot string,
	cwd string,
) (draftCommitmentScope, error) {
	layout, err := hostlayout.Resolve(hostEnvironment(), releaseRoot)
	if err != nil {
		return draftCommitmentScope{}, fmt.Errorf(
			"resolve draft host layout: %w",
			err,
		)
	}
	targets := layout.Targets()
	committedTargets := make(
		[]draftCommitmentTarget,
		0,
		len(targets),
	)
	for root, path := range targets {
		committedTargets = append(committedTargets, draftCommitmentTarget{
			Root: root,
			Path: path,
		})
	}
	return draftCommitmentScope{
		WorkingDirectory: cwd,
		ReleaseRoot:      releaseRoot,
		SourceRoot:       layout.Source(),
		TransactionState: layout.State(),
		Targets:          committedTargets,
	}, nil
}

func newMachineDraftSnapshotBuilder(
	releaseRoot string,
	cwd string,
) releaseSnapshotBuilder {
	builder := newReleaseSnapshotBuilderWithResolver(
		func() (string, error) { return releaseRoot, nil },
		cwd,
	)
	builder.client = func() codexstate.Client { return nil }
	return builder
}

func publicDraftReview(
	desired draftDesiredState,
	preview lifecycle.Preview,
	onboarding mcpcatalog.OnboardingPreview,
	applicable bool,
	confirmation string,
) draftReviewResponse {
	return draftReviewResponse{
		SchemaVersion:  draftProtocolVersion,
		Kind:           draftReviewResponseKind,
		StateSemantics: draftStateSemantics,
		Desired:        desired,
		Preview:        publicDraftSemanticPreview(preview),
		Onboarding:     publicDraftOnboarding(desired, onboarding),
		Apply: draftApplyAvailability{
			CommandAvailable: applicable,
			Confirmation:     confirmation,
		},
	}
}

func publicDraftSemanticPreview(
	preview lifecycle.Preview,
) draftSemanticPreview {
	result := emptyDraftSemanticPreview()
	for _, operation := range preview.Filesystem.Operations {
		result.Filesystem.Operations = append(
			result.Filesystem.Operations,
			draftFilesystemOperation{
				ComponentID: operation.ComponentID,
				UnitID:      operation.UnitID,
				Kind:        operation.Kind,
			},
		)
	}
	result.Configuration = publicDraftConfiguration(preview)
	result.MCP = publicDraftMCP(preview)
	for _, intent := range preview.Diagnostics.Intents {
		result.Diagnostics.Intents = append(
			result.Diagnostics.Intents,
			draftDiagnosticsIntent{
				ComponentID: intent.ComponentID,
				Events:      intent.Events,
				Feedback:    intent.Feedback,
			},
		)
	}
	result.Diagnostics.Executable = preview.Diagnostics.Executable
	return result
}

func emptyDraftSemanticPreview() draftSemanticPreview {
	return draftSemanticPreview{
		Filesystem: draftFilesystemPreview{
			Operations: []draftFilesystemOperation{},
		},
		Configuration: draftConfigurationPreview{
			Changes:       []draftConfigurationChange{},
			Issues:        []draftConfigurationIssue{},
			ManualActions: []draftConfigurationManualAction{},
			Notices:       []draftConfigurationNotice{},
		},
		MCP: draftMCPPreview{
			Intents:    []draftMCPIntent{},
			Migrations: []draftMCPMigration{},
		},
		Diagnostics: draftDiagnosticsPreview{
			Intents: []draftDiagnosticsIntent{},
		},
	}
}

func publicDraftConfiguration(
	preview lifecycle.Preview,
) draftConfigurationPreview {
	result := draftConfigurationPreview{
		Changes:       []draftConfigurationChange{},
		Issues:        []draftConfigurationIssue{},
		ManualActions: []draftConfigurationManualAction{},
		Notices:       []draftConfigurationNotice{},
	}
	for _, change := range preview.Configuration.Changes {
		result.Changes = append(result.Changes, draftConfigurationChange{
			ResourceID: change.ResourceID, ComponentID: change.ComponentID,
			UnitID: change.UnitID, Kind: change.Kind,
		})
	}
	for _, issue := range preview.Configuration.Issues {
		result.Issues = append(result.Issues, draftConfigurationIssue{
			ResourceID: issue.ResourceID, ComponentID: issue.ComponentID,
			UnitID: issue.UnitID, Kind: issue.Kind, Reason: issue.Reason,
		})
	}
	for _, action := range preview.Configuration.ManualActions {
		result.ManualActions = append(
			result.ManualActions,
			draftConfigurationManualAction{
				ResourceID: action.ResourceID, ComponentID: action.ComponentID,
				Kind: action.Kind, Reason: action.Reason,
			},
		)
	}
	for _, notice := range preview.Configuration.Notices {
		result.Notices = append(result.Notices, draftConfigurationNotice{
			ResourceID: notice.ResourceID, ComponentID: notice.ComponentID,
			Reason: notice.Reason,
		})
	}
	return result
}

func publicDraftMCP(preview lifecycle.Preview) draftMCPPreview {
	result := draftMCPPreview{
		Intents:    []draftMCPIntent{},
		Migrations: []draftMCPMigration{},
		Blocking:   preview.MCP.Blocking,
	}
	for _, intent := range preview.MCP.Intents {
		result.Intents = append(result.Intents, draftMCPIntent{
			ComponentID: intent.ComponentID, ServerID: intent.ServerID,
			ProfileID: intent.ProfileID, Kind: intent.Kind, Reason: intent.Reason,
		})
	}
	for _, migration := range preview.MCP.Migrations {
		result.Migrations = append(result.Migrations, draftMCPMigration{
			ComponentID: migration.ComponentID, State: migration.State,
			Reason:            migration.Reason,
			RequiresMigration: migration.RequiresMigration,
			Conflict:          migration.Conflict,
		})
	}
	return result
}

func publicDraftOnboarding(
	desired draftDesiredState,
	preview mcpcatalog.OnboardingPreview,
) draftOnboardingPreview {
	credentials := make(map[mcpcatalog.ServerID]credentialcatalog.InstanceID)
	for _, selection := range desired.MCP {
		credentials[selection.ServerID] = selection.CredentialInstanceID
	}
	result := draftOnboardingPreview{
		Connections: []draftOnboardingConnection{},
		Executable:  preview.Executable,
	}
	for _, connection := range preview.Connections {
		result.Connections = append(
			result.Connections,
			draftOnboardingConnection{
				ServerID: connection.ServerID, ServerName: connection.ServerName,
				ProfileID:            connection.Profile.ID,
				ProfileName:          connection.Profile.Name,
				Transport:            connection.Profile.Transport,
				Authentication:       connection.Profile.Authentication.Kind,
				Adapters:             append([]domain.ComponentID(nil), connection.Adapters...),
				CredentialInstanceID: credentials[connection.ServerID],
			},
		)
	}
	return result
}
