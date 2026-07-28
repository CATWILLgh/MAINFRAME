package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

const releaseCommitmentKind = "mainframe-release-review-commitment"

var releaseConfirmationPattern = regexp.MustCompile(
	`^sha256:[0-9a-f]{64}$`,
)

type releaseCommitmentScope struct {
	ReleasePath      string `json:"release_path"`
	UserBin          string `json:"user_bin"`
	TransactionState string `json:"transaction_state"`
}

type releaseCommitmentEnvelope struct {
	SchemaVersion int                      `json:"schema_version"`
	Kind          string                   `json:"kind"`
	Request       releaseApplyRequest      `json:"request"`
	Release       executor.ReleaseIdentity `json:"release"`
	Scope         releaseCommitmentScope   `json:"scope"`
	Operation     domain.Operation         `json:"operation"`
	Claim         *linkownership.Claim     `json:"claim,omitempty"`
}

func releaseReviewCommitment(
	request releaseApplyRequest,
	preview executor.Preview,
	claim *linkownership.Claim,
	scope releaseCommitmentScope,
) (string, error) {
	if err := validateReleaseCommitmentInput(
		request,
		preview,
		scope,
	); err != nil {
		return "", err
	}
	envelope := releaseCommitmentEnvelope{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseCommitmentKind,
		Request:       request,
		Release:       preview.Release,
		Scope:         scope,
		Operation:     preview.Plan.Operations[0],
		Claim:         cloneReleaseClaim(claim),
	}
	payload, err := json.Marshal(envelope)
	if err != nil {
		return "", fmt.Errorf("encode release review commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return fmt.Sprintf("sha256:%x", digest), nil
}

func validateReleaseCommitmentInput(
	request releaseApplyRequest,
	preview executor.Preview,
	scope releaseCommitmentScope,
) error {
	if scope.ReleasePath == "" ||
		scope.UserBin == "" ||
		scope.TransactionState == "" {
		return errors.New("release review scope is incomplete")
	}
	if request.ReleaseID != preview.Release.ID ||
		request.IndexSHA256 != preview.Release.IndexSHA256 ||
		len(preview.Desired) != 1 ||
		preview.Desired[0] != "mainframe-cli" ||
		len(preview.Plan.Operations) != 1 {
		return errors.New("release review is not bound to one launcher change")
	}
	operation := preview.Plan.Operations[0]
	if operation.ComponentID != "mainframe-cli" ||
		operation.UnitID != "mainframe-cli.binary" ||
		operation.Artifact.Location != (domain.Location{
			Root: domain.RootUserBin, Path: "mainframe",
		}) ||
		operation.SourcePath != "bin/mainframe" ||
		(operation.Kind != domain.OperationInstall &&
			operation.Kind != domain.OperationAdopt &&
			operation.Kind != domain.OperationReplace) {
		return errors.New("release review contains an unsupported operation")
	}
	return nil
}

func cloneReleaseClaim(claim *linkownership.Claim) *linkownership.Claim {
	if claim == nil {
		return nil
	}
	result := *claim
	return &result
}

func releaseCommitmentsEqual(left, right string) bool {
	return len(left) == len(right) &&
		subtle.ConstantTimeCompare([]byte(left), []byte(right)) == 1
}
