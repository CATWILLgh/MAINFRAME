package main

import (
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const (
	releaseProtocolVersion       = 1
	releaseChangeKind            = "mainframe-release-change"
	releaseApplyKind             = "mainframe-release-apply"
	releaseReviewKind            = "mainframe-release-review"
	releaseApplyResultKind       = "mainframe-release-apply-result"
	releaseOperationImport       = "import-and-activate"
	releaseOperationActivate     = "activate-cached"
	releaseIntegrityNotice       = "Local release hashes verify integrity, not publisher identity."
	releasePredictedTargetNotice = "The launcher already points to this unpublished cache path; repair it before import."
	releaseRecoveryRequiredError = "an unfinished transaction requires recovery before release review"
)

type releaseChangeRequest struct {
	SchemaVersion int    `json:"schema_version"`
	Kind          string `json:"kind"`
	Operation     string `json:"operation"`
	SourcePath    string `json:"source_path,omitempty"`
	ReleaseID     string `json:"release_id,omitempty"`
	IndexSHA256   string `json:"index_sha256,omitempty"`
}

type releaseApplyRequest struct {
	SchemaVersion int    `json:"schema_version"`
	Kind          string `json:"kind"`
	Operation     string `json:"operation"`
	SourcePath    string `json:"source_path,omitempty"`
	ReleaseID     string `json:"release_id"`
	IndexSHA256   string `json:"index_sha256"`
}

type releaseReviewResponse struct {
	SchemaVersion    int                       `json:"schema_version"`
	Kind             string                    `json:"kind"`
	Target           executor.ReleaseIdentity  `json:"target"`
	Previous         *executor.ReleaseIdentity `json:"previous,omitempty"`
	Operations       []planOperation           `json:"operations"`
	Applicable       bool                      `json:"applicable"`
	RecoveryRequired bool                      `json:"recovery_required"`
	Notices          []string                  `json:"notices"`
	ApplyRequest     *releaseApplyRequest      `json:"apply_request,omitempty"`
	ExpectedReview   string                    `json:"expected_review,omitempty"`
}

type releaseApplyResponse struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Active        string   `json:"active"`
	Warnings      []string `json:"warnings"`
}

func decodeReleaseChange(input io.Reader) (releaseChangeRequest, error) {
	request, err := decodeStrictJSON[releaseChangeRequest](input)
	if err != nil {
		return releaseChangeRequest{}, err
	}
	if request.SchemaVersion != releaseProtocolVersion {
		return releaseChangeRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != releaseChangeKind {
		return releaseChangeRequest{}, errors.New("request kind is unsupported")
	}
	if err := validateReleaseChangeShape(request); err != nil {
		return releaseChangeRequest{}, err
	}
	return request, nil
}

func decodeReleaseApply(input io.Reader) (releaseApplyRequest, error) {
	request, err := decodeStrictJSON[releaseApplyRequest](input)
	if err != nil {
		return releaseApplyRequest{}, err
	}
	if request.SchemaVersion != releaseProtocolVersion {
		return releaseApplyRequest{}, fmt.Errorf(
			"unsupported schema version %d",
			request.SchemaVersion,
		)
	}
	if request.Kind != releaseApplyKind {
		return releaseApplyRequest{}, errors.New("request kind is unsupported")
	}
	if !releasecontract.ValidReleaseIdentity(
		request.ReleaseID,
		request.IndexSHA256,
	) {
		return releaseApplyRequest{}, errors.New("release identity is invalid")
	}
	change := releaseChangeRequest{
		Operation: request.Operation, SourcePath: request.SourcePath,
		ReleaseID: request.ReleaseID, IndexSHA256: request.IndexSHA256,
	}
	if request.Operation == releaseOperationImport {
		change.ReleaseID = ""
		change.IndexSHA256 = ""
	}
	if err := validateReleaseChangeShape(change); err != nil {
		return releaseApplyRequest{}, err
	}
	return request, nil
}

func validateReleaseChangeShape(request releaseChangeRequest) error {
	switch request.Operation {
	case releaseOperationImport:
		if !validAbsoluteReleasePath(request.SourcePath) ||
			request.ReleaseID != "" ||
			request.IndexSHA256 != "" {
			return errors.New("import request must contain only an absolute source_path")
		}
	case releaseOperationActivate:
		if request.SourcePath != "" ||
			!releasecontract.ValidReleaseIdentity(
				request.ReleaseID,
				request.IndexSHA256,
			) {
			return errors.New("cached activation requires one exact release identity")
		}
	default:
		return errors.New("release operation is unsupported")
	}
	return nil
}

func validAbsoluteReleasePath(path string) bool {
	return path != "" &&
		!strings.ContainsRune(path, '\x00') &&
		filepath.IsAbs(path) &&
		filepath.Clean(path) == path
}
