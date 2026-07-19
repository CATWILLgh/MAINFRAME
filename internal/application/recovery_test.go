package application

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestRecoveryServiceClosesEverySession(t *testing.T) {
	closeErr := errors.New("close failed")
	recoverErr := errors.New("recover failed")
	tests := []struct {
		name       string
		recoverErr error
		closeErr   error
	}{
		{name: "success"},
		{name: "close warning", closeErr: closeErr},
		{name: "joined failures", recoverErr: recoverErr, closeErr: closeErr},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			session := &fakeRecoverySession{
				recoverErr: test.recoverErr,
				closeErr:   test.closeErr,
			}
			service, err := NewRecovery(
				&fakeRecoveryExecutorFactory{session: session},
			)
			if err != nil {
				t.Fatalf("NewRecovery() error = %v", err)
			}

			result, err := service.Recover()

			if session.recovers != 1 || session.closes != 1 {
				t.Fatalf(
					"recovers/closes = %d/%d, want 1/1",
					session.recovers,
					session.closes,
				)
			}
			if test.recoverErr != nil && !errors.Is(err, test.recoverErr) {
				t.Fatalf("Recover() error = %v", err)
			}
			if test.closeErr == nil {
				return
			}
			if test.recoverErr != nil {
				if !errors.Is(err, test.closeErr) {
					t.Fatalf("Recover() error = %v", err)
				}
				return
			}
			if err != nil || len(result.Warnings) != 1 ||
				!strings.Contains(result.Warnings[0], closeErr.Error()) {
				t.Fatalf("Recover() = %#v, %v", result, err)
			}
		})
	}
}

func TestRecoveryServiceRejectsUnavailableExecutor(t *testing.T) {
	openErr := errors.New("open failed")
	tests := []struct {
		name    string
		factory *fakeRecoveryExecutorFactory
	}{
		{name: "open error", factory: &fakeRecoveryExecutorFactory{err: openErr}},
		{name: "nil session", factory: &fakeRecoveryExecutorFactory{}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			service, err := NewRecovery(test.factory)
			if err != nil {
				t.Fatalf("NewRecovery() error = %v", err)
			}

			if _, err := service.Recover(); err == nil {
				t.Fatal("Recover() accepted an unavailable executor")
			}
			if test.factory.opens != 1 {
				t.Fatalf("factory opens = %d, want 1", test.factory.opens)
			}
		})
	}
}

func TestApplyRecoversBeforeOpeningSourcePinnedExecutor(t *testing.T) {
	events := []string{}
	recoverySession := &fakeRecoverySession{events: &events}
	recoveryFactory := &fakeRecoveryExecutorFactory{
		session: recoverySession,
		events:  &events,
	}
	applySession := &fakeApplySession{events: &events}
	applyFactory := &fakeApplyExecutorFactory{
		session: applySession,
		events:  &events,
	}
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	service, err := New(builder, applyFactory, recoveryFactory)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.Apply(reviewed); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}

	want := []string{
		"open recovery",
		"recover",
		"close recovery",
		"open apply",
		"apply",
		"close apply",
	}
	if strings.Join(events, ",") != strings.Join(want, ",") {
		t.Fatalf("events = %#v, want %#v", events, want)
	}
}

func TestApplyStopsBeforeSourcePinnedExecutorWhenRecoveryFails(t *testing.T) {
	recoverErr := errors.New("recovery failed")
	recoverySession := &fakeRecoverySession{recoverErr: recoverErr}
	recoveryFactory := &fakeRecoveryExecutorFactory{session: recoverySession}
	applyFactory := &fakeApplyExecutorFactory{session: &fakeApplySession{}}
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	service, err := New(builder, applyFactory, recoveryFactory)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	result, err := service.Apply(reviewed)

	if !errors.Is(err, recoverErr) {
		t.Fatalf("Apply() error = %v", err)
	}
	if len(result.Warnings) != 0 {
		t.Fatalf("Apply() result = %#v", result)
	}
	if applyFactory.opens != 0 {
		t.Fatalf("apply factory opens = %d, want 0", applyFactory.opens)
	}
}

func TestApplyPreservesRecoveryWarnings(t *testing.T) {
	recoveryFactory := &fakeRecoveryExecutorFactory{
		session: &fakeRecoverySession{
			result: executor.Result{Warnings: []string{"recovered warning"}},
		},
	}
	applyFactory := &fakeApplyExecutorFactory{
		session: &fakeApplySession{result: executor.Result{
			Warnings: []string{"apply warning"},
		}},
	}
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	service, err := New(builder, applyFactory, recoveryFactory)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	result, err := service.Apply(reviewed)

	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	want := []string{"recovered warning", "apply warning"}
	if strings.Join(result.Warnings, ",") != strings.Join(want, ",") {
		t.Fatalf("warnings = %#v, want %#v", result.Warnings, want)
	}
}
