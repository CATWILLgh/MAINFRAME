//go:build darwin || linux

package main

import (
	"encoding/json"
	"fmt"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecache"
	"github.com/CATWILLgh/MAINFRAME/internal/tui"
)

type releaseReviewFunc func(releaseChangeRequest) (releaseReviewResponse, error)
type releaseApplyFunc func(releaseApplyRequest, string) (releaseApplyResponse, error)
type releaseListFunc func() ([]tui.ReleaseSummary, error)

type releaseAdapter struct {
	review releaseReviewFunc
	apply  releaseApplyFunc
	list   releaseListFunc
}

func newReleaseAdapter() releaseAdapter {
	return releaseAdapter{
		review: reviewReleaseChange,
		apply:  applyReleaseChange,
		list:   listCachedReleases,
	}
}

func (adapter releaseAdapter) List() ([]tui.ReleaseSummary, error) {
	return adapter.list()
}

func (adapter releaseAdapter) ReviewImport(
	sourcePath string,
) (tui.ReleaseReview, error) {
	response, err := adapter.review(releaseChangeRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseChangeKind,
		Operation:     releaseOperationImport,
		SourcePath:    sourcePath,
	})
	if err != nil {
		return tui.ReleaseReview{}, err
	}
	return releaseReviewToTUI(response), nil
}

func (adapter releaseAdapter) ReviewActivateCached(
	releaseID, indexSHA256 string,
) (tui.ReleaseReview, error) {
	response, err := adapter.review(releaseChangeRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseChangeKind,
		Operation:     releaseOperationActivate,
		ReleaseID:     releaseID,
		IndexSHA256:   indexSHA256,
	})
	if err != nil {
		return tui.ReleaseReview{}, err
	}
	return releaseReviewToTUI(response), nil
}

func (adapter releaseAdapter) Apply(review tui.ReleaseReview) error {
	if !review.HasApplyTarget() {
		return fmt.Errorf("release review is not applicable")
	}
	request, err := decodeReleaseApplyRequest(review.ApplyRequest())
	if err != nil {
		return fmt.Errorf("release apply request rejected: %w", err)
	}
	if _, err := adapter.apply(request, review.Confirmation()); err != nil {
		return err
	}
	return nil
}

func releaseReviewToTUI(
	response releaseReviewResponse,
) tui.ReleaseReview {
	operations := make([]tui.ReleaseOperation, 0, len(response.Operations))
	for _, operation := range response.Operations {
		operations = append(operations, tui.ReleaseOperation{
			ComponentID: string(operation.ComponentID),
			Kind:        string(operation.Kind),
			SourcePath:  string(operation.SourcePath),
		})
	}
	review := tui.ReleaseReview{
		Target: tui.ReleaseIdentity{
			ReleaseID:   response.Target.ID,
			IndexSHA256: response.Target.IndexSHA256,
		},
		Operations:       operations,
		Applicable:       response.Applicable,
		RecoveryRequired: response.RecoveryRequired,
		Notices:          append([]string(nil), response.Notices...),
	}
	if response.Previous != nil {
		review.Previous = &tui.ReleaseIdentity{
			ReleaseID:   response.Previous.ID,
			IndexSHA256: response.Previous.IndexSHA256,
		}
	}
	if response.ApplyRequest != nil {
		encoded, err := json.Marshal(response.ApplyRequest)
		if err == nil {
			review = review.WithApplyRequest(encoded, response.ExpectedReview)
		}
	}
	return review
}

func decodeReleaseApplyRequest(encoded []byte) (releaseApplyRequest, error) {
	var request releaseApplyRequest
	if err := json.Unmarshal(encoded, &request); err != nil {
		return releaseApplyRequest{}, err
	}
	return request, nil
}

func listCachedReleases() ([]tui.ReleaseSummary, error) {
	environment := hostEnvironment()
	layout, err := resolveHostLayout(environment)
	if err != nil {
		return nil, err
	}
	store, err := releasecache.New(layout.Data())
	if err != nil {
		return nil, fmt.Errorf("open release store: %w", err)
	}
	entries, err := store.List()
	if err != nil {
		return nil, err
	}
	activeID, activeSHA := activeReleaseIdentity(layout, store)
	summaries := make([]tui.ReleaseSummary, 0, len(entries))
	for _, entry := range entries {
		summaries = append(summaries, tui.ReleaseSummary{
			ReleaseID:   entry.ReleaseID,
			IndexSHA256: entry.IndexSHA256,
			Active:      entry.ReleaseID == activeID && entry.IndexSHA256 == activeSHA,
		})
	}
	return summaries, nil
}

func activeReleaseIdentity(
	layout hostlayout.Layout,
	store releasecache.Store,
) (string, string) {
	registry, err := executor.ReadUnixOwnership(layout.State())
	if err != nil {
		return "", ""
	}
	launcherClaim, exists := registry.ClaimAt(releaseLauncherTarget)
	if !exists ||
		launcherClaim.ComponentID != "mainframe-cli" ||
		launcherClaim.UnitID != "mainframe-cli.binary" {
		return "", ""
	}
	return launcherClaim.ReleaseID, launcherClaim.IndexSHA256
}

func resolveHostLayout(
	environment hostlayout.Environment,
) (hostlayout.Layout, error) {
	return hostlayout.Resolve(environment, string(filepath.Separator))
}
