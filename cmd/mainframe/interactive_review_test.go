package main

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInteractiveReviewDoesNotOpenMutationState(t *testing.T) {
	for _, test := range []struct {
		name      string
		snapshots application.SnapshotBuilder
		wantError bool
	}{
		{
			name: "successful review",
			snapshots: staticInteractiveSnapshot{
				snapshot: application.Snapshot{
					Release: executor.ReleaseIdentity{
						ID:          "release",
						IndexSHA256: applyRuntimeDigest(1),
					},
					Lifecycle: interactiveDiagnosticsLifecycle(t),
				},
			},
		},
		{
			name:      "failed review",
			snapshots: staticInteractiveSnapshot{err: errors.New("snapshot failed")},
			wantError: true,
		},
	} {
		t.Run(test.name, func(t *testing.T) {
			fixture := newInteractiveReviewFixture(t, test.snapshots)
			reviewed, err := fixture.reviewer.Review(application.Request{
				Components: []domain.ComponentID{domain.ComponentClaudeCode},
				Diagnostics: diagnostics.Desired{
					Configured: true,
					Events:     true,
				},
			})
			if (err != nil) != test.wantError {
				t.Fatalf("Review() = %#v, %v", reviewed, err)
			}
			if !test.wantError && !reviewed.Semantic().Diagnostics.Executable {
				t.Fatal("reviewed diagnostics remained non-executable")
			}
			if fixture.apply.opens != 0 || fixture.recovery.opens != 0 {
				t.Fatalf(
					"factory opens = apply %d, recovery %d",
					fixture.apply.opens,
					fixture.recovery.opens,
				)
			}
			if _, err := os.Stat(fixture.stateRoot); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("review created mutation state: %v", err)
			}
		})
	}
}

type interactiveReviewFixture struct {
	reviewer  interactivePlanReviewer
	apply     *countingApplyFactory
	recovery  *countingRecoveryFactory
	stateRoot string
}

func newInteractiveReviewFixture(
	t *testing.T,
	snapshots application.SnapshotBuilder,
) interactiveReviewFixture {
	t.Helper()
	home := canonicalTempDir(t)
	stateBase := filepath.Join(canonicalTempDir(t), "state")
	releaseRoot := canonicalTempDir(t)
	environment := hostlayout.Environment{
		LookupEnv: func(name string) (string, bool) {
			if name == "XDG_STATE_HOME" {
				return stateBase, true
			}
			return "", false
		},
		UserHomeDir: func() (string, error) { return home, nil },
		GOOS:        "darwin",
	}
	recoveryLayout, err := hostlayout.ResolveRecovery(environment)
	if err != nil {
		t.Fatalf("ResolveRecovery() error = %v", err)
	}
	applyFactory := &countingApplyFactory{delegate: productionApplyExecutorFactory{
		resolveRoot: func() (string, error) { return releaseRoot, nil },
		environment: environment,
	}}
	recoveryFactory := &countingRecoveryFactory{
		delegate: productionRecoveryExecutorFactory{layout: recoveryLayout},
	}
	service, err := application.New(snapshots, applyFactory, recoveryFactory)
	if err != nil {
		t.Fatalf("application.New() error = %v", err)
	}
	targets, err := lifecycle.New(previewOwnershipModel(t), domain.ObservedState{})
	if err != nil {
		t.Fatalf("lifecycle.New() error = %v", err)
	}
	return interactiveReviewFixture{
		reviewer: interactivePlanReviewer{targets: targets, service: service},
		apply:    applyFactory, recovery: recoveryFactory,
		stateRoot: filepath.Join(stateBase, "mainframe"),
	}
}

func interactiveDiagnosticsLifecycle(t *testing.T) lifecycle.Service {
	t.Helper()
	resource := diagnosticsObservationExactResource(
		domain.ComponentClaudeCode,
		domain.RootClaudeConfig,
	)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		&diagnosticsObservationHost{},
	)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	service, err := lifecycle.NewWithInspection(
		previewOwnershipModel(t),
		domain.ObservedState{},
		inspection,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspection() error = %v", err)
	}
	return service
}

type staticInteractiveSnapshot struct {
	snapshot application.Snapshot
	err      error
}

func (builder staticInteractiveSnapshot) Build(
	application.Request,
) (application.Snapshot, error) {
	return builder.snapshot, builder.err
}

type countingApplyFactory struct {
	delegate application.ApplyExecutorFactory
	opens    int
}

func (factory *countingApplyFactory) Open(
	refresher executor.Refresher,
) (application.ApplySession, error) {
	factory.opens++
	return factory.delegate.Open(refresher)
}

type countingRecoveryFactory struct {
	delegate application.RecoveryExecutorFactory
	opens    int
}

func (factory *countingRecoveryFactory) Open() (
	application.RecoverySession,
	error,
) {
	factory.opens++
	return factory.delegate.Open()
}
