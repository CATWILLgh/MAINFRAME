package main

import (
	"slices"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestReleaseReviewCommitmentIsDeterministicAndBindsObservedState(
	t *testing.T,
) {
	request := releaseApplyRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseApplyKind,
		Operation:     releaseOperationActivate,
		ReleaseID:     "release-b",
		IndexSHA256:   strings.Repeat("b", 64),
	}
	preview := releaseCommitmentPreview()
	scope := releaseCommitmentScope{
		ReleasePath:      "/data/mainframe/releases/release-b/" + strings.Repeat("b", 64),
		UserBin:          "/home/user/.local/bin",
		TransactionState: "/home/user/.local/state/mainframe",
	}
	claim := &linkownership.Claim{
		UnitID: "mainframe-cli.binary", ComponentID: "mainframe-cli",
		Target:      domain.Location{Root: domain.RootUserBin, Path: "mainframe"},
		RawTarget:   "/data/mainframe/releases/release-a/old/bin/mainframe",
		ReleaseID:   "release-a",
		IndexSHA256: strings.Repeat("a", 64),
	}

	first, err := releaseReviewCommitment(request, preview, claim, scope)
	if err != nil {
		t.Fatalf("releaseReviewCommitment() error = %v", err)
	}
	repeated, err := releaseReviewCommitment(request, preview, claim, scope)
	if err != nil || repeated != first || !releaseConfirmationPattern.MatchString(first) {
		t.Fatalf("repeat commitment = %q, %v; want %q", repeated, err, first)
	}

	changed := preview
	changed.Plan.Operations = append(
		[]domain.Operation(nil),
		preview.Plan.Operations...,
	)
	changed.Plan.Operations[0].Artifact.LinkInode++
	drifted, err := releaseReviewCommitment(request, changed, claim, scope)
	if err != nil || releaseCommitmentsEqual(first, drifted) {
		t.Fatalf("link drift commitment = %q, %v", drifted, err)
	}

	changedClaim := *claim
	changedClaim.RawTarget += ".changed"
	drifted, err = releaseReviewCommitment(
		request,
		preview,
		&changedClaim,
		scope,
	)
	if err != nil || releaseCommitmentsEqual(first, drifted) {
		t.Fatalf("claim drift commitment = %q, %v", drifted, err)
	}
}

func TestReleaseReviewRequiresRecoveryBeforeConfirmation(t *testing.T) {
	request := releaseApplyRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseApplyKind,
		Operation:     releaseOperationActivate,
		ReleaseID:     "release-b",
		IndexSHA256:   strings.Repeat("b", 64),
	}
	response, err := buildReleaseReviewResponse(
		request,
		releaseObservation{
			preview: releaseCommitmentPreview(),
			journal: &executor.Journal{},
		},
	)
	if err != nil {
		t.Fatalf("buildReleaseReviewResponse() error = %v", err)
	}
	if !response.RecoveryRequired ||
		response.Applicable ||
		response.ApplyRequest != nil ||
		response.ExpectedReview != "" ||
		!slices.Contains(
			response.Notices,
			releaseRecoveryRequiredError,
		) {
		t.Fatalf("recovery review = %#v", response)
	}
}

func releaseCommitmentPreview() executor.Preview {
	return executor.Preview{
		Release: executor.ReleaseIdentity{
			ID: "release-b", IndexSHA256: strings.Repeat("b", 64),
		},
		Desired: []domain.ComponentID{"mainframe-cli"},
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: "mainframe-cli",
			UnitID:      "mainframe-cli.binary",
			Kind:        domain.OperationReplace,
			Artifact: domain.Artifact{
				Location: domain.Location{
					Root: domain.RootUserBin, Path: "mainframe",
				},
				Ownership:  domain.OwnershipManagedPrevious,
				RawTarget:  "/data/mainframe/releases/release-a/old/bin/mainframe",
				LinkDevice: 1, LinkInode: 2,
			},
			SourcePath: "bin/mainframe",
		}}},
	}
}
