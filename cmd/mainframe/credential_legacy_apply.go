//go:build darwin || linux

package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
)

const (
	legacyTransferApplySchemaVersion = 1
	legacyTransferApplyRequestKind   = "mainframe-legacy-credential-transfer-apply"
	legacyTransferApplyResultKind    = "mainframe-legacy-credential-transfer-apply-result"
	legacyTransferCommitmentKind     = "mainframe-legacy-credential-transfer-commitment"
)

type legacyTransferApplyRequest struct {
	SchemaVersion    int                           `json:"schema_version"`
	Kind             string                        `json:"kind"`
	ReleaseID        string                        `json:"release_id"`
	SourceCommitment string                        `json:"source_commitment"`
	Instances        []credentialInstance          `json:"instances"`
	Choices          []legacyTransferChoiceRequest `json:"choices"`
}

type legacyTransferApplyResponse struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Warnings      []string `json:"warnings"`
}

type legacyTransferCommitmentEnvelope struct {
	SchemaVersion        int                                 `json:"schema_version"`
	Kind                 string                              `json:"kind"`
	CredentialCommitment string                              `json:"credential_commitment"`
	ApplyRequest         legacyTransferApplyRequest          `json:"apply_request"`
	SourceAccounting     credentialmigration.AccountingState `json:"source_accounting"`
	ContentAccounting    credentialmigration.AccountingState `json:"content_accounting"`
	Summary              legacyTransferReviewSummary         `json:"summary"`
}

func runLegacyCredentialTransferApply(
	confirmation string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	if !credentialConfirmationPattern.MatchString(confirmation) {
		fmt.Fprintln(
			errorOutput,
			"credentials legacy-apply: confirmation digest is invalid",
		)
		return 2
	}
	request, err := decodeLegacyTransferApply(input)
	if err != nil {
		fmt.Fprintf(
			errorOutput,
			"credentials legacy-apply: invalid request: %v\n",
			err,
		)
		return 2
	}
	response, err := applyLegacyCredentialTransfer(request, confirmation)
	if err != nil {
		fmt.Fprintf(errorOutput, "credentials legacy-apply: %v\n", err)
		return 1
	}
	if err := encodeCredentialResponse(output, response); err != nil {
		fmt.Fprintf(errorOutput, "credentials legacy-apply: %v\n", err)
		return 1
	}
	return 0
}

func decodeLegacyTransferApply(
	input io.Reader,
) (legacyTransferApplyRequest, error) {
	request, err := decodeStrictJSON[legacyTransferApplyRequest](input)
	if err != nil {
		return legacyTransferApplyRequest{}, err
	}
	if request.SchemaVersion != legacyTransferApplySchemaVersion {
		return legacyTransferApplyRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != legacyTransferApplyRequestKind {
		return legacyTransferApplyRequest{}, errors.New(
			"request kind is unsupported",
		)
	}
	if request.ReleaseID == "" ||
		!credentialConfirmationPattern.MatchString(request.SourceCommitment) ||
		request.Instances == nil ||
		request.Choices == nil {
		return legacyTransferApplyRequest{}, errors.New(
			"release_id, source_commitment, instances, and choices are required",
		)
	}
	for _, choice := range request.Choices {
		if choice.Proposal.SectionPath == nil {
			return legacyTransferApplyRequest{}, errors.New(
				"proposal section_path must be an array",
			)
		}
	}
	return request, nil
}

func applyLegacyCredentialTransfer(
	request legacyTransferApplyRequest,
	confirmation string,
) (legacyTransferApplyResponse, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	plan, err := inspectLegacyCredentialTransferPlan(
		snapshot.release,
		snapshot.root,
		hostEnvironment(),
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	if plan.ReleaseID != request.ReleaseID {
		return legacyTransferApplyResponse{}, errors.New(
			"legacy transfer release is stale; run review again",
		)
	}
	sourceCommitment, err := credentialmigration.
		LegacyTransferSourceCommitment(plan)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	if !credentialCommitmentsEqual(
		sourceCommitment,
		request.SourceCommitment,
	) {
		return legacyTransferApplyResponse{}, errors.New(
			"legacy credential sources changed; run review again",
		)
	}
	return applyReviewedLegacyTransfer(
		plan,
		request,
		confirmation,
	)
}

func applyReviewedLegacyTransfer(
	plan credentialmigration.LegacyTransferPlan,
	request legacyTransferApplyRequest,
	confirmation string,
) (legacyTransferApplyResponse, error) {
	session, err := buildLegacyCredentialMachineSession(
		request.SourceCommitment,
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	desired, err := buildDesiredCredentialInstances(
		request.Instances,
		session.definitions,
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	draft := legacyDraftFromApplyRequest(request, session.current)
	review, err := credentialmigration.ReviewLegacyTransferDraft(
		plan,
		session.current,
		session.definitions,
		draft,
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	response := publicLegacyTransferReview(plan.ReleaseID, review)
	if !legacyTransferReviewApplicable(plan, response) ||
		!reflect.DeepEqual(desired.All(), review.Desired.All()) {
		return legacyTransferApplyResponse{}, errors.New(
			"legacy transfer is no longer applicable; run review again",
		)
	}
	normalized := normalizedLegacyTransferApplyRequest(
		legacyReviewRequestFromApply(request, draft),
		response,
		request.SourceCommitment,
	)
	if !sameLegacyApplyRequest(normalized, request) {
		return legacyTransferApplyResponse{}, errors.New(
			"legacy apply request is not normalized; run review again",
		)
	}
	return commitLegacyCredentialTransfer(
		session,
		plan,
		request,
		response,
		review.Desired,
		confirmation,
	)
}

func sameLegacyApplyRequest(
	expected, actual legacyTransferApplyRequest,
) bool {
	expectedJSON, expectedErr := json.Marshal(expected)
	actualJSON, actualErr := json.Marshal(actual)
	return expectedErr == nil &&
		actualErr == nil &&
		bytes.Equal(expectedJSON, actualJSON)
}

func commitLegacyCredentialTransfer(
	session credentialMachineSession,
	plan credentialmigration.LegacyTransferPlan,
	request legacyTransferApplyRequest,
	response legacyTransferReviewResponse,
	desired credentialcatalog.Instances,
	confirmation string,
) (legacyTransferApplyResponse, error) {
	reviewed, err := session.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	if !reviewed.CredentialOnlyApplicable() ||
		!sameCredentialChanges(reviewed.CredentialChanges(), response.Changes) {
		return legacyTransferApplyResponse{}, errors.New(
			"credential catalog changed; run review again",
		)
	}
	credentialCommitment, err := credentialReviewCommitment(
		reviewed.Executable(),
		desired,
		session.scope,
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	current, err := legacyTransferApplyCommitment(
		credentialCommitment,
		request,
		plan,
		response.Summary,
	)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	if !credentialCommitmentsEqual(current, confirmation) {
		return legacyTransferApplyResponse{}, errors.New(
			"review confirmation is stale; run review again",
		)
	}
	result, err := session.service.ApplyCredentials(reviewed)
	if err != nil {
		return legacyTransferApplyResponse{}, err
	}
	return legacyTransferApplyResponse{
		SchemaVersion: legacyTransferApplySchemaVersion,
		Kind:          legacyTransferApplyResultKind,
		Applied:       true,
		Warnings:      append([]string{}, result.Warnings...),
	}, nil
}

func legacyDraftFromApplyRequest(
	request legacyTransferApplyRequest,
	current credentialcatalog.Instances,
) credentialmigration.LegacyTransferDraft {
	currentIDs := make(map[credentialcatalog.InstanceID]struct{})
	for _, instance := range current.All() {
		currentIDs[instance.ID] = struct{}{}
	}
	var additions []credentialcatalog.Instance
	for _, instance := range request.Instances {
		internal := internalCredentialInstance(instance)
		if _, exists := currentIDs[internal.ID]; !exists {
			additions = append(additions, internal)
		}
	}
	choices := make([]credentialmigration.LegacyTransferChoice, len(request.Choices))
	for index, choice := range request.Choices {
		choices[index] = internalLegacyTransferChoice(choice)
	}
	return credentialmigration.LegacyTransferDraft{
		ReleaseID: request.ReleaseID, NewInstances: additions, Choices: choices,
	}
}

func legacyReviewRequestFromApply(
	request legacyTransferApplyRequest,
	draft credentialmigration.LegacyTransferDraft,
) legacyTransferReviewRequest {
	return legacyTransferReviewRequest{
		SchemaVersion: legacyTransferReviewSchemaVersion,
		Kind:          legacyTransferReviewRequestKind,
		ReleaseID:     request.ReleaseID,
		NewInstances:  publicCredentialInstances(draft.NewInstances),
		Choices:       cloneLegacyChoiceRequests(request.Choices),
	}
}

func legacyTransferReviewApplicable(
	plan credentialmigration.LegacyTransferPlan,
	response legacyTransferReviewResponse,
) bool {
	return plan.SourceAccounting == credentialmigration.AccountingComplete &&
		plan.ContentAccounting != credentialmigration.AccountingBlocked &&
		plan.MigrationReadiness != credentialmigration.ReadinessBlocked &&
		response.Summary.Pending == 0 &&
		len(response.Changes) > 0
}

func legacyTargetReference(
	instances []credentialInstance,
	target legacyTransferTargetRequest,
) string {
	for _, instance := range instances {
		if instance.ID != target.InstanceID {
			continue
		}
		for _, binding := range instance.Credentials {
			if binding.RoleID == target.RoleID {
				return binding.Secret.Name
			}
		}
	}
	return ""
}

func cloneLegacyChoiceRequests(
	source []legacyTransferChoiceRequest,
) []legacyTransferChoiceRequest {
	result := make([]legacyTransferChoiceRequest, len(source))
	for index, choice := range source {
		result[index] = choice
		result[index].Proposal.SectionPath = append(
			[]string(nil),
			choice.Proposal.SectionPath...,
		)
	}
	return result
}

func legacyTransferApplyCommitment(
	credentialCommitment string,
	request legacyTransferApplyRequest,
	plan credentialmigration.LegacyTransferPlan,
	summary legacyTransferReviewSummary,
) (string, error) {
	payload, err := json.Marshal(legacyTransferCommitmentEnvelope{
		SchemaVersion:        legacyTransferApplySchemaVersion,
		Kind:                 legacyTransferCommitmentKind,
		CredentialCommitment: credentialCommitment,
		ApplyRequest:         request,
		SourceAccounting:     plan.SourceAccounting,
		ContentAccounting:    plan.ContentAccounting,
		Summary:              summary,
	})
	if err != nil {
		return "", fmt.Errorf("encode legacy transfer commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(digest[:]), nil
}

func sameCredentialChanges(
	internal []credentialcatalog.InstanceChange,
	public []credentialChangeResponse,
) bool {
	if len(internal) != len(public) {
		return false
	}
	for index, change := range internal {
		if !reflect.DeepEqual(publicCredentialChange(change), public[index]) {
			return false
		}
	}
	return true
}
