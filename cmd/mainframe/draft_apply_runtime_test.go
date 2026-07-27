package main

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestApplyDraftRuntimeRejectsStaleDigestBeforeApply(t *testing.T) {
	var events []string
	dependencies, request := fakeDraftApplyDependencies(t, &events)

	_, err := applyDraftWithDependencies(
		request,
		"sha256:"+strings.Repeat("0", 64),
		dependencies,
	)

	if err == nil {
		t.Fatal("applyDraftWithDependencies() accepted stale confirmation")
	}
	if !reflect.DeepEqual(events, []string{"recover", "review"}) {
		t.Fatalf("events = %#v", events)
	}
}

func TestApplyDraftRuntimeRecoversBeforeReviewAndPreservesWarnings(
	t *testing.T,
) {
	var events []string
	dependencies, request := fakeDraftApplyDependencies(t, &events)
	candidate, err := dependencies.review(request)
	if err != nil {
		t.Fatal(err)
	}
	confirmation, err := draftReviewCommitment(
		candidate.desired,
		candidate.preview,
		candidate.scope,
	)
	if err != nil {
		t.Fatal(err)
	}
	events = nil

	result, err := applyDraftWithDependencies(
		request,
		confirmation,
		dependencies,
	)

	if err != nil {
		t.Fatalf("applyDraftWithDependencies() error = %v", err)
	}
	if !reflect.DeepEqual(events, []string{"recover", "review", "apply"}) {
		t.Fatalf("events = %#v", events)
	}
	if !reflect.DeepEqual(
		result.Warnings,
		[]string{
			"recovery completed with warnings",
			"application completed with warnings",
		},
	) {
		t.Fatalf("warnings = %#v", result.Warnings)
	}
	encoded := strings.Join(result.Warnings, "\n")
	for _, forbidden := range []string{
		"secret-warning-marker",
		"/private/recovery/path",
		"/private/apply/path",
	} {
		if strings.Contains(encoded, forbidden) {
			t.Fatalf("warnings expose %q: %q", forbidden, encoded)
		}
	}
}

func fakeDraftApplyDependencies(
	t *testing.T,
	events *[]string,
) (draftApplyDependencies, draftReviewRequest) {
	t.Helper()
	desired := draftDesiredState{
		Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
		MCP:               []draftMCPSelection{},
		DiagnosticsPolicy: draftDiagnosticsPolicy,
	}
	preview := draftCommitmentPreview(t, []byte(`{"value":"after"}`))
	scope := draftCommitmentScope{
		WorkingDirectory: "/work",
		ReleaseRoot:      "/release",
		SourceRoot:       "/release/bundles",
		TransactionState: "/state",
		Targets: []draftCommitmentTarget{{
			Root: domain.RootOpenCodeConfig, Path: "/config/opencode",
		}},
	}
	request := draftReviewRequest{
		SchemaVersion: draftProtocolVersion,
		Kind:          draftRequestKind,
		Desired:       desired,
	}
	return draftApplyDependencies{
		recover: func() ([]string, error) {
			*events = append(*events, "recover")
			return []string{
				"recovery /private/recovery/path secret-warning-marker",
			}, nil
		},
		review: func(draftReviewRequest) (draftApplyCandidate, error) {
			*events = append(*events, "review")
			return draftApplyCandidate{
				desired:    desired,
				preview:    preview,
				scope:      scope,
				applicable: true,
				applyConfirmed: func() (executor.Result, error) {
					*events = append(*events, "apply")
					return executor.Result{
						Warnings: []string{
							"apply /private/apply/path secret-warning-marker",
						},
					}, nil
				},
			}, nil
		},
	}, request
}
