//go:build darwin || linux

package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

const (
	legacyTransferReviewSchemaVersion = 1
	legacyTransferReviewRequestKind   = "mainframe-legacy-credential-transfer-draft"
	legacyTransferReviewResponseKind  = "mainframe-legacy-credential-transfer-review"
	legacyTransferAfterKind           = "mainframe-credential-instances"
)

type legacyTransferReviewRequest struct {
	SchemaVersion int                           `json:"schema_version"`
	Kind          string                        `json:"kind"`
	ReleaseID     string                        `json:"release_id"`
	NewInstances  []credentialInstance          `json:"new_instances"`
	Choices       []legacyTransferChoiceRequest `json:"choices"`
}

type legacyTransferChoiceRequest struct {
	Proposal            legacyProposalIdentityRequest            `json:"proposal"`
	ExpectedOccurrences int                                      `json:"expected_occurrences"`
	Action              credentialmigration.TransferChoiceAction `json:"action"`
	Target              legacyTransferTargetRequest              `json:"target"`
	RenameConfirmed     bool                                     `json:"rename_confirmed"`
	SkipReason          credentialmigration.TransferSkipReason   `json:"skip_reason,omitempty"`
}

type legacyProposalIdentityRequest struct {
	ComponentID   domain.ComponentID             `json:"component_id"`
	ResourceID    string                         `json:"resource_id"`
	SourceRole    credentialmigration.SourceRole `json:"source_role"`
	SectionPath   []string                       `json:"section_path"`
	ReferenceName string                         `json:"reference_name"`
}

type legacyTransferTargetRequest struct {
	InstanceID string `json:"instance_id,omitempty"`
	RoleID     string `json:"role_id,omitempty"`
}

type legacyTransferReviewResponse struct {
	SchemaVersion               int                            `json:"schema_version"`
	Kind                        string                         `json:"kind"`
	ReleaseID                   string                         `json:"release_id"`
	MigrationPerformed          bool                           `json:"migration_performed"`
	ApplyAvailable              bool                           `json:"apply_available"`
	ReferenceChoicesComplete    bool                           `json:"reference_choices_complete"`
	ManualContentReviewRequired bool                           `json:"manual_content_review_required"`
	RetirementReady             bool                           `json:"retirement_ready"`
	Summary                     legacyTransferReviewSummary    `json:"summary"`
	Choices                     []legacyTransferChoiceResponse `json:"choices"`
	Changes                     []credentialChangeResponse     `json:"changes"`
	After                       legacyTransferAfterResponse    `json:"after"`
	ApplyRequest                *legacyTransferApplyRequest    `json:"apply_request,omitempty"`
	ExpectedReview              string                         `json:"expected_review,omitempty"`
}

type legacyTransferReviewSummary struct {
	Total       int `json:"total"`
	Transferred int `json:"transferred"`
	Skipped     int `json:"skipped"`
	Pending     int `json:"pending"`
}

type legacyTransferChoiceResponse struct {
	Proposal    legacyProposalIdentityRequest                 `json:"proposal"`
	Occurrences int                                           `json:"occurrences"`
	Disposition credentialmigration.TransferChoiceDisposition `json:"disposition"`
	Target      legacyTransferTargetRequest                   `json:"target"`
	SkipReason  credentialmigration.TransferSkipReason        `json:"skip_reason,omitempty"`
}

type legacyTransferAfterResponse struct {
	SchemaVersion int                  `json:"schema_version"`
	Kind          string               `json:"kind"`
	Instances     []credentialInstance `json:"instances"`
}

func writeLegacyCredentialTransferReview(
	request legacyTransferReviewRequest,
	output io.Writer,
) error {
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
	runtime, err := loadCredentialRuntime(snapshot.root, snapshot.release)
	if err != nil {
		return err
	}
	response, err := reviewLegacyCredentialTransferDraft(
		plan,
		runtime.snapshot.Instances(),
		runtime.definitions,
		request,
	)
	if err != nil {
		return err
	}
	response, err = attachLegacyTransferApply(
		plan,
		request,
		response,
	)
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(response); err != nil {
		return fmt.Errorf("encode legacy transfer review: %w", err)
	}
	return nil
}

func attachLegacyTransferApply(
	plan credentialmigration.LegacyTransferPlan,
	request legacyTransferReviewRequest,
	response legacyTransferReviewResponse,
) (legacyTransferReviewResponse, error) {
	if !legacyTransferReviewApplicable(plan, response) {
		return response, nil
	}
	sourceCommitment, err := credentialmigration.LegacyTransferSourceCommitment(plan)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	session, err := buildLegacyCredentialMachineSession(sourceCommitment)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	desired, err := buildDesiredCredentialInstances(
		response.After.Instances,
		session.definitions,
	)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	reviewed, err := session.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	if !reviewed.CredentialOnlyApplicable() ||
		!sameCredentialChanges(reviewed.CredentialChanges(), response.Changes) {
		return legacyTransferReviewResponse{}, errors.New(
			"legacy credential review changed while commitment was built",
		)
	}
	credentialCommitment, err := credentialReviewCommitment(
		reviewed.Executable(), desired, session.scope,
	)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	applyRequest := normalizedLegacyTransferApplyRequest(
		request, response, sourceCommitment,
	)
	commitment, err := legacyTransferApplyCommitment(
		credentialCommitment,
		applyRequest,
		plan,
		response.Summary,
	)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	response.ApplyAvailable = true
	response.ApplyRequest = &applyRequest
	response.ExpectedReview = commitment
	return response, nil
}

func normalizedLegacyTransferApplyRequest(
	request legacyTransferReviewRequest,
	response legacyTransferReviewResponse,
	sourceCommitment string,
) legacyTransferApplyRequest {
	return legacyTransferApplyRequest{
		SchemaVersion:    legacyTransferApplySchemaVersion,
		Kind:             legacyTransferApplyRequestKind,
		ReleaseID:        request.ReleaseID,
		SourceCommitment: sourceCommitment,
		Instances:        append([]credentialInstance(nil), response.After.Instances...),
		Choices: normalizedLegacyChoiceRequests(
			response.Choices,
			response.After.Instances,
		),
	}
}

func normalizedLegacyChoiceRequests(
	choices []legacyTransferChoiceResponse,
	instances []credentialInstance,
) []legacyTransferChoiceRequest {
	result := make([]legacyTransferChoiceRequest, len(choices))
	for index, choice := range choices {
		result[index] = legacyTransferChoiceRequest{
			Proposal:            choice.Proposal,
			ExpectedOccurrences: choice.Occurrences,
			Target:              choice.Target,
			SkipReason:          choice.SkipReason,
		}
		if choice.Disposition == credentialmigration.ChoiceSkipped {
			result[index].Action = credentialmigration.TransferChoiceSkip
			continue
		}
		result[index].Action = credentialmigration.TransferChoiceTransfer
		result[index].RenameConfirmed = legacyTargetReference(
			instances,
			choice.Target,
		) != choice.Proposal.ReferenceName
	}
	return result
}

func decodeLegacyTransferReview(
	input io.Reader,
) (legacyTransferReviewRequest, error) {
	request, err := decodeStrictJSON[legacyTransferReviewRequest](input)
	if err != nil {
		return legacyTransferReviewRequest{}, err
	}
	if request.SchemaVersion != legacyTransferReviewSchemaVersion {
		return legacyTransferReviewRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != legacyTransferReviewRequestKind {
		return legacyTransferReviewRequest{}, errors.New(
			"request kind is unsupported",
		)
	}
	if request.ReleaseID == "" ||
		request.NewInstances == nil ||
		request.Choices == nil {
		return legacyTransferReviewRequest{}, errors.New(
			"release_id, new_instances, and choices are required",
		)
	}
	for _, choice := range request.Choices {
		if choice.Proposal.SectionPath == nil {
			return legacyTransferReviewRequest{}, errors.New(
				"proposal section_path must be an array",
			)
		}
	}
	return request, nil
}

func reviewLegacyCredentialTransferDraft(
	plan credentialmigration.LegacyTransferPlan,
	current credentialcatalog.Instances,
	definitions credentialcatalog.Definitions,
	request legacyTransferReviewRequest,
) (legacyTransferReviewResponse, error) {
	newInstances := make(
		[]credentialcatalog.Instance,
		len(request.NewInstances),
	)
	for index, instance := range request.NewInstances {
		newInstances[index] = internalCredentialInstance(instance)
	}
	choices := make(
		[]credentialmigration.LegacyTransferChoice,
		len(request.Choices),
	)
	for index, choice := range request.Choices {
		choices[index] = internalLegacyTransferChoice(choice)
	}
	review, err := credentialmigration.ReviewLegacyTransferDraft(
		plan,
		current,
		definitions,
		credentialmigration.LegacyTransferDraft{
			ReleaseID:    request.ReleaseID,
			NewInstances: newInstances,
			Choices:      choices,
		},
	)
	if err != nil {
		return legacyTransferReviewResponse{}, err
	}
	return publicLegacyTransferReview(plan.ReleaseID, review), nil
}

func internalLegacyTransferChoice(
	choice legacyTransferChoiceRequest,
) credentialmigration.LegacyTransferChoice {
	return credentialmigration.LegacyTransferChoice{
		Proposal: credentialmigration.LegacyProposalIdentity{
			ComponentID: choice.Proposal.ComponentID,
			ResourceID:  choice.Proposal.ResourceID,
			SourceRole:  choice.Proposal.SourceRole,
			SectionPath: append(
				[]string(nil),
				choice.Proposal.SectionPath...,
			),
			ReferenceName: choice.Proposal.ReferenceName,
		},
		ExpectedOccurrences: choice.ExpectedOccurrences,
		Action:              choice.Action,
		TargetInstanceID: credentialcatalog.InstanceID(
			choice.Target.InstanceID,
		),
		TargetRoleID:    credentialcatalog.RoleID(choice.Target.RoleID),
		RenameConfirmed: choice.RenameConfirmed,
		SkipReason:      choice.SkipReason,
	}
}

func publicLegacyTransferReview(
	releaseID string,
	review credentialmigration.LegacyTransferDraftReview,
) legacyTransferReviewResponse {
	changes := make([]credentialChangeResponse, len(review.Changes))
	for index, change := range review.Changes {
		changes[index] = publicCredentialChange(change)
	}
	return legacyTransferReviewResponse{
		SchemaVersion:               legacyTransferReviewSchemaVersion,
		Kind:                        legacyTransferReviewResponseKind,
		ReleaseID:                   releaseID,
		MigrationPerformed:          false,
		ApplyAvailable:              false,
		ReferenceChoicesComplete:    review.PendingProposals == 0,
		ManualContentReviewRequired: review.ManualContentReviewRequired,
		RetirementReady:             review.RetirementReady,
		Summary: legacyTransferReviewSummary{
			Total:       review.TotalProposals,
			Transferred: review.TransferredProposals,
			Skipped:     review.SkippedProposals,
			Pending:     review.PendingProposals,
		},
		Choices: publicLegacyTransferChoices(review.Choices),
		Changes: changes,
		After: legacyTransferAfterResponse{
			SchemaVersion: 1,
			Kind:          legacyTransferAfterKind,
			Instances:     publicCredentialInstances(review.Desired.All()),
		},
	}
}

func publicLegacyTransferChoices(
	choices []credentialmigration.LegacyTransferChoiceResult,
) []legacyTransferChoiceResponse {
	result := make([]legacyTransferChoiceResponse, len(choices))
	for index, choice := range choices {
		result[index] = legacyTransferChoiceResponse{
			Proposal: legacyProposalIdentityRequest{
				ComponentID: choice.Proposal.ComponentID,
				ResourceID:  choice.Proposal.ResourceID,
				SourceRole:  choice.Proposal.SourceRole,
				SectionPath: append(
					[]string(nil),
					choice.Proposal.SectionPath...,
				),
				ReferenceName: choice.Proposal.ReferenceName,
			},
			Occurrences: choice.Occurrences,
			Disposition: choice.Disposition,
			Target: legacyTransferTargetRequest{
				InstanceID: string(choice.TargetInstanceID),
				RoleID:     string(choice.TargetRoleID),
			},
			SkipReason: choice.SkipReason,
		}
	}
	return result
}
