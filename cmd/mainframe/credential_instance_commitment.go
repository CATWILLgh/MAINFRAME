package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

type credentialCommitment struct {
	SchemaVersion int                         `json:"schema_version"`
	Kind          string                      `json:"kind"`
	Release       executor.ReleaseIdentity    `json:"release"`
	Scope         credentialCommitmentScope   `json:"scope"`
	ResourceIDs   []string                    `json:"resource_ids"`
	Mutation      credentialCommittedMutation `json:"mutation"`
	DesiredSHA256 string                      `json:"desired_sha256"`
}

type credentialCommitmentScope struct {
	CredentialTarget string `json:"credential_target"`
	TransactionState string `json:"transaction_state"`
	ReleaseRoot      string `json:"release_root"`
}

type credentialCommittedMutation struct {
	Disposition string                    `json:"disposition"`
	Root        string                    `json:"root"`
	Path        string                    `json:"path"`
	Before      credentialCommittedBefore `json:"before"`
	After       credentialCommittedAfter  `json:"after"`
}

type credentialCommittedBefore struct {
	Exists           bool   `json:"exists"`
	SHA256           string `json:"sha256"`
	Mode             uint32 `json:"mode"`
	Device           uint64 `json:"device"`
	Inode            uint64 `json:"inode"`
	BirthSeconds     int64  `json:"birth_seconds"`
	BirthNanoseconds int64  `json:"birth_nanoseconds"`
}

type credentialCommittedAfter struct {
	Exists bool   `json:"exists"`
	SHA256 string `json:"sha256"`
	Mode   uint32 `json:"mode"`
}

func credentialReviewCommitment(
	preview executor.Preview,
	desired credentialcatalog.Instances,
	scope credentialCommitmentScope,
) (string, error) {
	if err := validateCredentialCommitmentInput(
		preview,
		desired,
		scope,
	); err != nil {
		return "", err
	}
	transition := preview.Configuration.Transitions()[0]
	mutation := transition.Mutations[0]
	desiredPayload, err := credentialcatalog.EncodeInstances(desired)
	if err != nil {
		return "", fmt.Errorf("encode desired credential instances: %w", err)
	}
	envelope := buildCredentialCommitment(
		preview,
		scope,
		transition.ResourceIDs,
		mutation,
		desiredPayload,
	)
	payload, err := json.Marshal(envelope)
	if err != nil {
		return "", fmt.Errorf("encode credential review commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return fmt.Sprintf("sha256:%x", digest), nil
}

func validateCredentialCommitmentInput(
	preview executor.Preview,
	desired credentialcatalog.Instances,
	scope credentialCommitmentScope,
) error {
	if scope.CredentialTarget == "" ||
		scope.TransactionState == "" ||
		scope.ReleaseRoot == "" {
		return errors.New("credential review scope is incomplete")
	}
	if len(preview.Desired) != 0 ||
		len(preview.Plan.Operations) != 0 ||
		len(preview.Configuration.Preconditions()) != 0 ||
		len(preview.Configuration.Materializations()) != 0 ||
		credentialcatalog.ValidateInstancesOnlyPlan(
			preview.Configuration,
			desired,
		) != nil {
		return errors.New(
			"review contains changes outside credential metadata",
		)
	}
	return nil
}

func buildCredentialCommitment(
	preview executor.Preview,
	scope credentialCommitmentScope,
	resourceIDs []string,
	mutation configuration.FileMutation,
	desiredPayload []byte,
) credentialCommitment {
	afterDigest := sha256.Sum256(mutation.After.Content)
	desiredDigest := sha256.Sum256(desiredPayload)
	return credentialCommitment{
		SchemaVersion: credentialInstanceProtocolVersion,
		Kind:          credentialCommitmentKind,
		Release:       preview.Release,
		Scope:         scope,
		ResourceIDs:   append([]string(nil), resourceIDs...),
		Mutation: credentialCommittedMutation{
			Disposition: string(mutation.Disposition),
			Root:        string(mutation.Target.Root),
			Path:        string(mutation.Target.Path),
			Before: credentialCommittedBefore{
				Exists: mutation.Before.Exists, SHA256: mutation.Before.SHA256,
				Mode: mutation.Before.Mode, Device: mutation.Before.Device,
				Inode:            mutation.Before.Inode,
				BirthSeconds:     mutation.Before.BirthSeconds,
				BirthNanoseconds: mutation.Before.BirthNanoseconds,
			},
			After: credentialCommittedAfter{
				Exists: mutation.After.Exists,
				SHA256: fmt.Sprintf("%x", afterDigest),
				Mode:   mutation.After.Mode,
			},
		},
		DesiredSHA256: fmt.Sprintf("%x", desiredDigest),
	}
}

func credentialCommitmentsEqual(left, right string) bool {
	return len(left) == len(right) &&
		subtle.ConstantTimeCompare([]byte(left), []byte(right)) == 1
}
