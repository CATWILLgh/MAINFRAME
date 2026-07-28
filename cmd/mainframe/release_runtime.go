//go:build darwin || linux

package main

import (
	"errors"
	"fmt"
	"path/filepath"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/releaseactivation"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecache"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

var releaseLauncherTarget = domain.Location{
	Root: domain.RootUserBin,
	Path: "mainframe",
}

type releaseObservation struct {
	entry    releasecache.Entry
	release  releasecontract.Release
	layout   hostlayout.Layout
	preview  executor.Preview
	claim    *linkownership.Claim
	previous *executor.ReleaseIdentity
	journal  *executor.Journal
}

type releaseActivationRefresher struct {
	environment hostlayout.Environment
	store       releasecache.Store
	identity    executor.ReleaseIdentity
}

func reviewReleaseChange(
	request releaseChangeRequest,
) (releaseReviewResponse, error) {
	environment := hostEnvironment()
	store, err := openReleaseStore(environment)
	if err != nil {
		return releaseReviewResponse{}, err
	}
	applyRequest, entry, release, err := resolveReleaseReviewTarget(
		request,
		store,
	)
	if err != nil {
		return releaseReviewResponse{}, err
	}
	observation, err := observeRelease(
		environment,
		store,
		entry,
		release,
	)
	if err != nil {
		return releaseReviewResponse{}, err
	}
	return buildReleaseReviewResponse(applyRequest, observation)
}

func applyReleaseChange(
	request releaseApplyRequest,
	confirmation string,
) (releaseApplyResponse, error) {
	environment := hostEnvironment()
	store, err := openReleaseStore(environment)
	if err != nil {
		return releaseApplyResponse{}, err
	}
	observation, err := inspectReleaseApplyRequest(environment, store, request)
	if err != nil {
		return releaseApplyResponse{}, err
	}
	if observation.journal != nil {
		return releaseApplyResponse{}, errors.New(
			"release state changed after review; review again",
		)
	}
	if !releasePreviewApplicable(observation.preview) {
		return releaseApplyResponse{}, errors.New(
			"reviewed release change is no longer applicable; review again",
		)
	}
	expected, err := releaseReviewCommitment(
		request,
		observation.preview,
		observation.claim,
		releaseScope(observation),
	)
	if err != nil {
		return releaseApplyResponse{}, err
	}
	if !releaseCommitmentsEqual(confirmation, expected) {
		return releaseApplyResponse{}, errors.New(
			"release state changed after review; review again",
		)
	}
	if err := ensureReleaseApplyTarget(store, request); err != nil {
		return releaseApplyResponse{}, err
	}
	result, err := executeReleaseActivation(environment, store, observation)
	if err != nil {
		return releaseApplyResponse{}, err
	}
	return releaseApplyResponse{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseApplyResultKind,
		Applied:       true,
		Active:        filepath.Join(observation.entry.Path, "bin", "mainframe"),
		Warnings:      append([]string{}, result.Warnings...),
	}, nil
}

func openReleaseStore(
	environment hostlayout.Environment,
) (releasecache.Store, error) {
	layout, err := hostlayout.Resolve(
		environment,
		string(filepath.Separator),
	)
	if err != nil {
		return releasecache.Store{}, fmt.Errorf("resolve release store: %w", err)
	}
	store, err := releasecache.New(layout.Data())
	if err != nil {
		return releasecache.Store{}, fmt.Errorf("open release store: %w", err)
	}
	return store, nil
}

func resolveReleaseReviewTarget(
	request releaseChangeRequest,
	store releasecache.Store,
) (
	releaseApplyRequest,
	releasecache.Entry,
	releasecontract.Release,
	error,
) {
	if request.Operation == releaseOperationImport {
		release, err := releasecontract.Load(request.SourcePath)
		if err != nil {
			return releaseApplyRequest{}, releasecache.Entry{},
				releasecontract.Release{}, fmt.Errorf(
					"load local release: %w",
					err,
				)
		}
		entry, err := store.InspectImport(request.SourcePath)
		if err != nil {
			return releaseApplyRequest{}, releasecache.Entry{},
				releasecontract.Release{}, err
		}
		return normalizedReleaseApply(request, release), entry, release, nil
	}
	entry, err := store.Open(request.ReleaseID, request.IndexSHA256)
	if err != nil {
		return releaseApplyRequest{}, releasecache.Entry{},
			releasecontract.Release{}, err
	}
	release, err := releasecontract.Load(entry.Path)
	if err != nil {
		return releaseApplyRequest{}, releasecache.Entry{},
			releasecontract.Release{}, fmt.Errorf("load cached release: %w", err)
	}
	return normalizedReleaseApply(request, release), entry, release, nil
}

func normalizedReleaseApply(
	request releaseChangeRequest,
	release releasecontract.Release,
) releaseApplyRequest {
	return releaseApplyRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseApplyKind,
		Operation:     request.Operation,
		SourcePath:    request.SourcePath,
		ReleaseID:     release.ID,
		IndexSHA256:   release.IndexSHA256,
	}
}

func observeRelease(
	environment hostlayout.Environment,
	store releasecache.Store,
	entry releasecache.Entry,
	release releasecontract.Release,
) (releaseObservation, error) {
	layout, err := hostlayout.Resolve(environment, entry.Path)
	if err != nil {
		return releaseObservation{}, fmt.Errorf("resolve release layout: %w", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return releaseObservation{}, fmt.Errorf("open host namespace: %w", err)
	}
	registry, err := executor.ReadUnixOwnership(layout.State())
	if err != nil {
		return releaseObservation{}, fmt.Errorf("read ownership registry: %w", err)
	}
	preview, err := releaseactivation.BuildPreview(
		release,
		namespace.Filesystem(),
		namespace.Roots(),
		registry,
	)
	if err != nil {
		return releaseObservation{}, fmt.Errorf("build release activation preview: %w", err)
	}
	journal, err := executor.ReadUnixJournal(layout.State())
	if err != nil {
		return releaseObservation{}, fmt.Errorf("read transaction journal: %w", err)
	}
	claim, exists := registry.ClaimAt(releaseLauncherTarget)
	var claimPointer *linkownership.Claim
	if exists {
		claimPointer = &claim
	}
	return releaseObservation{
		entry: entry, release: release, layout: layout, preview: preview,
		claim:    claimPointer,
		previous: previousReleaseIdentity(store, claimPointer),
		journal:  journal,
	}, nil
}

func previousReleaseIdentity(
	store releasecache.Store,
	claim *linkownership.Claim,
) *executor.ReleaseIdentity {
	if claim == nil ||
		claim.ComponentID != "mainframe-cli" ||
		claim.UnitID != "mainframe-cli.binary" {
		return nil
	}
	entry, err := store.Open(claim.ReleaseID, claim.IndexSHA256)
	if err != nil ||
		claim.RawTarget != filepath.Join(entry.Path, "bin", "mainframe") {
		return nil
	}
	return &executor.ReleaseIdentity{
		ID: claim.ReleaseID, IndexSHA256: claim.IndexSHA256,
	}
}

func buildReleaseReviewResponse(
	request releaseApplyRequest,
	observation releaseObservation,
) (releaseReviewResponse, error) {
	response := releaseReviewResponse{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseReviewKind,
		Target:        observation.preview.Release,
		Previous:      observation.previous,
		Operations:    publicPlanResponse(observation.preview.Plan).Operations,
		Notices:       []string{releaseIntegrityNotice},
	}
	if observation.journal != nil {
		response.RecoveryRequired = true
		response.Notices = append(
			response.Notices,
			releaseRecoveryRequiredError,
		)
		return response, nil
	}
	if targetsUnpublishedRelease(request, observation) {
		response.Notices = append(
			response.Notices,
			releasePredictedTargetNotice,
		)
		return response, nil
	}
	if !releasePreviewApplicable(observation.preview) {
		return response, nil
	}
	commitment, err := releaseReviewCommitment(
		request,
		observation.preview,
		observation.claim,
		releaseScope(observation),
	)
	if err != nil {
		return releaseReviewResponse{}, err
	}
	response.Applicable = true
	response.ApplyRequest = &request
	response.ExpectedReview = commitment
	return response, nil
}

func targetsUnpublishedRelease(
	request releaseApplyRequest,
	observation releaseObservation,
) bool {
	if request.Operation != releaseOperationImport ||
		observation.entry.AlreadyPresent ||
		len(observation.preview.Plan.Operations) != 1 {
		return false
	}
	return observation.preview.Plan.Operations[0].Artifact.RawTarget ==
		filepath.Join(observation.entry.Path, "bin", "mainframe")
}

func releasePreviewApplicable(preview executor.Preview) bool {
	if len(preview.Plan.Operations) != 1 {
		return false
	}
	operation := preview.Plan.Operations[0]
	return operation.Kind == domain.OperationInstall ||
		operation.Kind == domain.OperationAdopt ||
		operation.Kind == domain.OperationReplace
}

func releaseScope(observation releaseObservation) releaseCommitmentScope {
	return releaseCommitmentScope{
		ReleasePath:      observation.entry.Path,
		UserBin:          observation.layout.Targets()[domain.RootUserBin],
		TransactionState: observation.layout.State(),
	}
}
