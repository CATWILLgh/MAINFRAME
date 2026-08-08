//go:build darwin || linux

package main

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/tui"
)

func TestReleaseAdapterRoundTripsApplyRequestAndConfirmation(t *testing.T) {
	wantApplyRequest := releaseApplyRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseApplyKind,
		Operation:     releaseOperationActivate,
		ReleaseID:     "release-a",
		IndexSHA256:   strings.Repeat("a", 64),
	}
	wantConfirmation := "sha256:" + strings.Repeat("0", 64)
	reviewCalls := 0
	applyCalls := 0
	var capturedRequest releaseApplyRequest
	var capturedConfirmation string
	adapter := releaseAdapter{
		review: func(request releaseChangeRequest) (releaseReviewResponse, error) {
			reviewCalls++
			return releaseReviewResponse{
				SchemaVersion: releaseProtocolVersion,
				Kind:          releaseReviewKind,
				Target: executor.ReleaseIdentity{
					ID: "release-a", IndexSHA256: strings.Repeat("a", 64),
				},
				Applicable:     true,
				ApplyRequest:   &wantApplyRequest,
				ExpectedReview: wantConfirmation,
			}, nil
		},
		apply: func(request releaseApplyRequest, confirmation string) (releaseApplyResponse, error) {
			applyCalls++
			capturedRequest = request
			capturedConfirmation = confirmation
			return releaseApplyResponse{Applied: true}, nil
		},
	}

	review, err := adapter.ReviewActivateCached(
		"release-a", strings.Repeat("a", 64),
	)
	if err != nil {
		t.Fatalf("ReviewActivateCached error = %v", err)
	}
	if reviewCalls != 1 {
		t.Fatalf("review called %d times, want 1", reviewCalls)
	}
	if !review.HasApplyTarget() {
		t.Fatal("review.HasApplyTarget() = false, want true")
	}
	if review.Confirmation() != wantConfirmation {
		t.Fatalf("Confirmation() = %q, want %q", review.Confirmation(), wantConfirmation)
	}
	var decoded releaseApplyRequest
	if err := json.Unmarshal(review.ApplyRequest(), &decoded); err != nil {
		t.Fatalf("ApplyRequest() not decodable: %v", err)
	}
	if decoded != wantApplyRequest {
		t.Fatalf("ApplyRequest() decoded = %#v, want %#v", decoded, wantApplyRequest)
	}

	if err := adapter.Apply(review); err != nil {
		t.Fatalf("Apply error = %v", err)
	}
	if applyCalls != 1 {
		t.Fatalf("apply called %d times, want 1", applyCalls)
	}
	if capturedRequest != wantApplyRequest {
		t.Fatalf("apply received request %#v, want %#v", capturedRequest, wantApplyRequest)
	}
	if capturedConfirmation != wantConfirmation {
		t.Fatalf("apply received confirmation %q, want %q", capturedConfirmation, wantConfirmation)
	}
}

func TestReleaseAdapterForwardsMutatedConfirmation(t *testing.T) {
	capturedConfirmation := "untouched"
	adapter := releaseAdapter{
		review: func(request releaseChangeRequest) (releaseReviewResponse, error) {
			return releaseReviewResponse{
				Applicable:     true,
				ApplyRequest:   &releaseApplyRequest{Operation: releaseOperationActivate, ReleaseID: "x", IndexSHA256: strings.Repeat("a", 64)},
				ExpectedReview: "sha256:" + strings.Repeat("1", 64),
			}, nil
		},
		apply: func(_ releaseApplyRequest, confirmation string) (releaseApplyResponse, error) {
			capturedConfirmation = confirmation
			return releaseApplyResponse{Applied: true}, nil
		},
	}

	review, err := adapter.ReviewActivateCached("x", strings.Repeat("a", 64))
	if err != nil {
		t.Fatalf("ReviewActivateCached: %v", err)
	}
	mutated := review.WithApplyRequest(
		review.ApplyRequest(),
		"sha256:"+strings.Repeat("9", 64),
	)
	if err := adapter.Apply(mutated); err != nil {
		t.Fatalf("Apply mutated: %v", err)
	}
	want := "sha256:" + strings.Repeat("9", 64)
	if capturedConfirmation != want {
		t.Fatalf("adapter forwarded %q, want %q — adapter must not recompute or mask the confirmation", capturedConfirmation, want)
	}
}

func TestReleaseAdapterApplyRejectsReviewWithoutApplyTarget(t *testing.T) {
	adapter := releaseAdapter{
		review: func(request releaseChangeRequest) (releaseReviewResponse, error) {
			return releaseReviewResponse{Applicable: false}, nil
		},
		apply: func(_ releaseApplyRequest, _ string) (releaseApplyResponse, error) {
			t.Fatal("apply must not be called for non-applicable review")
			return releaseApplyResponse{}, nil
		},
	}
	review, err := adapter.ReviewActivateCached("x", strings.Repeat("a", 64))
	if err != nil {
		t.Fatalf("ReviewActivateCached: %v", err)
	}
	if review.HasApplyTarget() {
		t.Fatal("non-applicable review should not have apply target")
	}
	if err := adapter.Apply(review); err == nil {
		t.Fatal("Apply on non-applicable review should error")
	}
}

func TestReleaseAdapterListMapsEntriesToSummaries(t *testing.T) {
	adapter := releaseAdapter{
		list: func() ([]tui.ReleaseSummary, error) {
			return []tui.ReleaseSummary{
				{ReleaseID: "alpha", IndexSHA256: strings.Repeat("a", 64), Active: true},
				{ReleaseID: "beta", IndexSHA256: strings.Repeat("b", 64)},
			}, nil
		},
	}
	summaries, err := adapter.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(summaries) != 2 {
		t.Fatalf("List = %v summaries, want 2", len(summaries))
	}
	if !summaries[0].Active {
		t.Fatalf("summaries[0].Active = false, want true")
	}
	if summaries[1].Active {
		t.Fatalf("summaries[1].Active = true, want false")
	}
}
