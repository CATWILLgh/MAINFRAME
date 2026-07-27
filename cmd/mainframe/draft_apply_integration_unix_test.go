//go:build darwin || linux

package main

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestDraftCommitmentAppliesExactHermeticTransactionOnce(t *testing.T) {
	fixture := newAntigravityMCPFixture(t)
	request := fixture.request("remote-api-key", true)
	reviewed, err := fixture.service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if !reviewed.Applicable() {
		t.Fatal("hermetic Context7 plan is not applicable")
	}
	desired := draftDesiredState{
		Adapters: []domain.ComponentID{domain.ComponentAntigravity2},
		MCP: []draftMCPSelection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters:             []domain.ComponentID{domain.ComponentAntigravity2},
			CredentialInstanceID: "context7-home",
		}},
		DiagnosticsPolicy: draftDiagnosticsPolicy,
	}
	scope := draftCommitmentScope{
		WorkingDirectory: t.TempDir(),
		ReleaseRoot:      t.TempDir(),
		SourceRoot:       t.TempDir(),
		TransactionState: t.TempDir(),
		Targets: []draftCommitmentTarget{{
			Root: domain.RootAntigravityConfig,
			Path: t.TempDir(),
		}},
	}
	confirmation, err := draftReviewCommitment(
		desired,
		reviewed.Executable(),
		scope,
	)
	if err != nil {
		t.Fatalf("draftReviewCommitment() error = %v", err)
	}
	if strings.Contains(confirmation, antigravityIntegrationSecret) {
		t.Fatal("confirmation contains resolved secret")
	}
	applyExactHermeticDraft(t, fixture, reviewed)
	assertRepeatedHermeticDraftIsNoOp(t, fixture, request)
}

func applyExactHermeticDraft(
	t *testing.T,
	fixture antigravityMCPFixture,
	reviewed application.ReviewedPlan,
) {
	t.Helper()
	if _, err := fixture.service.ApplyConfirmed(reviewed); err != nil {
		t.Fatalf("ApplyConfirmed() error = %v", err)
	}
	fixture.assertKeyedState(antigravityIntegrationSecret)
}

func assertRepeatedHermeticDraftIsNoOp(
	t *testing.T,
	fixture antigravityMCPFixture,
	request application.Request,
) {
	t.Helper()
	before, err := os.Stat(fixture.configPath)
	if err != nil {
		t.Fatal(err)
	}
	repeated, err := fixture.service.Review(request)
	if err != nil {
		t.Fatalf("repeat Review() error = %v", err)
	}
	if _, err := fixture.service.ApplyConfirmed(repeated); err != nil {
		t.Fatalf("repeat ApplyConfirmed() error = %v", err)
	}
	after, err := os.Stat(fixture.configPath)
	if err != nil {
		t.Fatal(err)
	}
	if !os.SameFile(before, after) {
		t.Fatal("repeated apply rewrote unchanged configuration")
	}
}
