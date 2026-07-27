package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

const draftCommitmentKind = "mainframe-draft-commitment"

type draftCommitmentScope struct {
	WorkingDirectory string                  `json:"working_directory"`
	ReleaseRoot      string                  `json:"release_root"`
	SourceRoot       string                  `json:"source_root"`
	TransactionState string                  `json:"transaction_state"`
	Targets          []draftCommitmentTarget `json:"targets"`
}

type draftCommitmentTarget struct {
	Root domain.RootID `json:"root"`
	Path string        `json:"path"`
}

type draftCommitmentEnvelope struct {
	SchemaVersion    int                                         `json:"schema_version"`
	Kind             string                                      `json:"kind"`
	Desired          draftDesiredState                           `json:"desired"`
	Release          executor.ReleaseIdentity                    `json:"release"`
	Scope            draftCommitmentScope                        `json:"scope"`
	Operations       []domain.Operation                          `json:"operations"`
	Transitions      []draftCommittedTransition                  `json:"transitions"`
	Preconditions    []configuration.ReadPrecondition            `json:"preconditions"`
	Materializations []configuration.SecretMaterializationRecipe `json:"materializations"`
}

type draftCommittedTransition struct {
	ResourceIDs []string                 `json:"resource_ids"`
	Mutations   []draftCommittedMutation `json:"mutations"`
}

type draftCommittedMutation struct {
	Disposition configuration.MutationDisposition `json:"disposition"`
	Target      domain.Location                   `json:"target"`
	Before      configuration.BeforeImage         `json:"before"`
	After       draftCommittedAfter               `json:"after"`
}

type draftCommittedAfter struct {
	Exists bool   `json:"exists"`
	SHA256 string `json:"sha256"`
	Mode   uint32 `json:"mode"`
}

func draftReviewCommitment(
	desired draftDesiredState,
	preview executor.Preview,
	scope draftCommitmentScope,
) (string, error) {
	if err := validateDraftCommitmentScope(scope); err != nil {
		return "", err
	}
	envelope := draftCommitmentEnvelope{
		SchemaVersion:    draftProtocolVersion,
		Kind:             draftCommitmentKind,
		Desired:          desired,
		Release:          preview.Release,
		Scope:            normalizedDraftCommitmentScope(scope),
		Operations:       append([]domain.Operation(nil), preview.Plan.Operations...),
		Transitions:      committedDraftTransitions(preview.Configuration),
		Preconditions:    preview.Configuration.Preconditions(),
		Materializations: preview.Configuration.Materializations(),
	}
	payload, err := json.Marshal(envelope)
	if err != nil {
		return "", fmt.Errorf("encode draft commitment: %w", err)
	}
	digest := sha256.Sum256(payload)
	return fmt.Sprintf("sha256:%x", digest), nil
}

func validateDraftCommitmentScope(scope draftCommitmentScope) error {
	if scope.WorkingDirectory == "" || scope.ReleaseRoot == "" ||
		scope.SourceRoot == "" || scope.TransactionState == "" ||
		len(scope.Targets) == 0 {
		return errors.New("draft commitment scope is incomplete")
	}
	return nil
}

func normalizedDraftCommitmentScope(
	scope draftCommitmentScope,
) draftCommitmentScope {
	result := scope
	result.Targets = append([]draftCommitmentTarget(nil), scope.Targets...)
	sort.Slice(result.Targets, func(left, right int) bool {
		if result.Targets[left].Root != result.Targets[right].Root {
			return result.Targets[left].Root < result.Targets[right].Root
		}
		return result.Targets[left].Path < result.Targets[right].Path
	})
	return result
}

func committedDraftTransitions(
	plan configuration.PreparedPlan,
) []draftCommittedTransition {
	source := plan.Transitions()
	result := make([]draftCommittedTransition, len(source))
	for index, transition := range source {
		result[index] = draftCommittedTransition{
			ResourceIDs: append([]string(nil), transition.ResourceIDs...),
			Mutations:   committedDraftMutations(transition.Mutations),
		}
	}
	return result
}

func committedDraftMutations(
	source []configuration.FileMutation,
) []draftCommittedMutation {
	result := make([]draftCommittedMutation, len(source))
	for index, mutation := range source {
		afterDigest := sha256.Sum256(mutation.After.Content)
		result[index] = draftCommittedMutation{
			Disposition: mutation.Disposition,
			Target:      mutation.Target,
			Before:      mutation.Before,
			After: draftCommittedAfter{
				Exists: mutation.After.Exists,
				SHA256: fmt.Sprintf("%x", afterDigest),
				Mode:   mutation.After.Mode,
			},
		}
	}
	return result
}

func draftCommitmentsEqual(left, right string) bool {
	return len(left) == len(right) &&
		subtle.ConstantTimeCompare([]byte(left), []byte(right)) == 1
}
