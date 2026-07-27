package main

import (
	"errors"
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

type draftApplyDependencies struct {
	recover func() ([]string, error)
	review  func(draftReviewRequest) (draftApplyCandidate, error)
}

type draftApplyCandidate struct {
	desired        draftDesiredState
	preview        executor.Preview
	scope          draftCommitmentScope
	applicable     bool
	applyConfirmed func() (executor.Result, error)
}

func applyDraft(
	request draftReviewRequest,
	confirmation string,
) (draftApplyResponse, error) {
	return applyDraftWithDependencies(
		request,
		confirmation,
		draftApplyDependencies{
			recover: recoverBeforeDraftApply,
			review:  reviewDraftForApply,
		},
	)
}

func applyDraftWithDependencies(
	request draftReviewRequest,
	confirmation string,
	dependencies draftApplyDependencies,
) (draftApplyResponse, error) {
	if dependencies.recover == nil || dependencies.review == nil {
		return draftApplyResponse{}, errors.New(
			"draft apply dependencies are unavailable",
		)
	}
	recovered, err := dependencies.recover()
	if err != nil {
		return draftApplyResponse{}, err
	}
	candidate, err := dependencies.review(request)
	if err != nil {
		return draftApplyResponse{}, err
	}
	if !candidate.applicable || candidate.applyConfirmed == nil {
		return draftApplyResponse{}, errors.New(
			"reviewed draft is no longer applicable",
		)
	}
	current, err := draftReviewCommitment(
		candidate.desired,
		candidate.preview,
		candidate.scope,
	)
	if err != nil {
		return draftApplyResponse{}, err
	}
	if !draftCommitmentsEqual(current, confirmation) {
		return draftApplyResponse{}, errors.New(
			"draft confirmation is stale; run review again",
		)
	}
	result, err := candidate.applyConfirmed()
	if err != nil {
		return draftApplyResponse{}, err
	}
	return draftApplyResponse{
		SchemaVersion: draftProtocolVersion,
		Kind:          draftApplyResponseKind,
		Applied:       true,
		Warnings:      publicDraftApplyWarnings(recovered, result.Warnings),
	}, nil
}

func publicDraftApplyWarnings(
	recovery []string,
	application []string,
) []string {
	warnings := []string{}
	if len(recovery) > 0 {
		warnings = append(warnings, "recovery completed with warnings")
	}
	if len(application) > 0 {
		warnings = append(warnings, "application completed with warnings")
	}
	return warnings
}

func reviewDraftForApply(
	request draftReviewRequest,
) (draftApplyCandidate, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return draftApplyCandidate{}, err
	}
	normalized, internal, _, err := normalizeDraftReviewRequest(
		snapshot.release.MCPCatalog,
		request,
	)
	if err != nil {
		return draftApplyCandidate{}, errors.New("desired state is invalid")
	}
	cwd, err := os.Getwd()
	if err != nil {
		return draftApplyCandidate{}, errors.New(
			"working directory is unavailable",
		)
	}
	service, reviewed, err := buildDraftApplyPlan(
		snapshot,
		cwd,
		internal,
	)
	if err != nil {
		return draftApplyCandidate{}, err
	}
	scope, err := buildDraftCommitmentScope(snapshot.root, cwd)
	if err != nil {
		return draftApplyCandidate{}, err
	}
	return draftApplyCandidate{
		desired:    normalized,
		preview:    reviewed.Executable(),
		scope:      scope,
		applicable: reviewed.Applicable(),
		applyConfirmed: func() (executor.Result, error) {
			return service.ApplyConfirmed(reviewed)
		},
	}, nil
}

func recoverBeforeDraftApply() ([]string, error) {
	service, err := buildRecoveryService()
	if err != nil {
		return nil, fmt.Errorf("build draft recovery: %w", err)
	}
	result, err := service.Recover()
	if err != nil {
		return nil, fmt.Errorf("recover before draft apply: %w", err)
	}
	return append([]string(nil), result.Warnings...), nil
}

func buildDraftApplyPlan(
	snapshot readOnlyReleaseSnapshot,
	cwd string,
	request application.Request,
) (application.Service, application.ReviewedPlan, error) {
	builder := newMachineDraftSnapshotBuilder(snapshot.root, cwd)
	identity := releaseIdentity(snapshot.release)
	builder.expectedRelease = &identity
	roots := &releaseRootSource{value: snapshot.root}
	service, err := buildApplyServiceWithSnapshotBuilder(roots, builder)
	if err != nil {
		return application.Service{}, application.ReviewedPlan{}, err
	}
	reviewed, err := service.Review(request)
	if err != nil {
		return application.Service{}, application.ReviewedPlan{}, err
	}
	return service, reviewed, nil
}
