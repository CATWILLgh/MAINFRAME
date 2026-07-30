package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
)

const (
	secretRetirementProtocolVersion = 1
	secretRetirementReviewKind      = "mainframe-credential-secret-retirement-review"
	secretRetirementApplyKind       = "mainframe-credential-secret-retirement-apply"
	secretRetirementResultKind      = "mainframe-credential-secret-retirement-apply-result"
	secretRetirementCommitmentKind  = "mainframe-credential-secret-retirement-commitment"
)

type secretRetirementApplyRequest struct {
	SchemaVersion      int                       `json:"schema_version"`
	Kind               string                    `json:"kind"`
	Secret             credentialSecretReference `json:"secret"`
	ExpectedGeneration string                    `json:"expected_generation"`
}

type secretRetirementReviewResponse struct {
	SchemaVersion  int                          `json:"schema_version"`
	Kind           string                       `json:"kind"`
	ApplyRequest   secretRetirementApplyRequest `json:"apply_request"`
	ExpectedReview string                       `json:"expected_review"`
}

type secretRetirementApplyResponse struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Warnings      []string `json:"warnings"`
}

type secretRetirementScope struct {
	ReleaseRoot      string `json:"release_root"`
	TransactionState string `json:"transaction_state"`
	CredentialRoot   string `json:"credential_root"`
	SecretStorePath  string `json:"secret_store_path"`
	HomeRoot         string `json:"home_root"`
	ClaudeRoot       string `json:"claude_root"`
	CodexRoot        string `json:"codex_root"`
	OpenCodeRoot     string `json:"opencode_root"`
	AntigravityRoot  string `json:"antigravity_root"`
}

type secretRetirementCommitmentEnvelope struct {
	SchemaVersion int                          `json:"schema_version"`
	Kind          string                       `json:"kind"`
	ApplyRequest  secretRetirementApplyRequest `json:"apply_request"`
	Scope         secretRetirementScope        `json:"scope"`
}

func decodeSecretRetirementApplyRequest(
	input io.Reader,
) (secretRetirementApplyRequest, error) {
	request, err := decodeStrictJSON[secretRetirementApplyRequest](input)
	if err != nil {
		return secretRetirementApplyRequest{}, err
	}
	if request.SchemaVersion != secretRetirementProtocolVersion {
		return secretRetirementApplyRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != secretRetirementApplyKind {
		return secretRetirementApplyRequest{}, errors.New(
			"request kind is unsupported",
		)
	}
	if request.Secret.Backend != string(credentialcatalog.BackendSecretEnvironment) ||
		request.Secret.Name == "" ||
		len(request.ExpectedGeneration) != 64 {
		return secretRetirementApplyRequest{}, errors.New(
			"secret retirement apply request is invalid",
		)
	}
	if _, err := hex.DecodeString(request.ExpectedGeneration); err != nil {
		return secretRetirementApplyRequest{}, errors.New(
			"secret retirement generation is invalid",
		)
	}
	return request, nil
}

func secretRetirementCommitment(
	request secretRetirementApplyRequest,
	scope secretRetirementScope,
) (string, error) {
	envelope := secretRetirementCommitmentEnvelope{
		SchemaVersion: secretRetirementProtocolVersion,
		Kind:          secretRetirementCommitmentKind,
		ApplyRequest:  request,
		Scope:         scope,
	}
	payload, err := json.Marshal(envelope)
	if err != nil {
		return "", fmt.Errorf("encode secret retirement commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(digest[:]), nil
}

func secretRetirementCommitmentsEqual(left, right string) bool {
	if len(left) != len(right) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(left), []byte(right)) == 1
}
