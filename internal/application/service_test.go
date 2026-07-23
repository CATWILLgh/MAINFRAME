package application

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

const testReleaseDigest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

func TestNewRejectsMissingDependencies(t *testing.T) {
	tests := []struct {
		name      string
		snapshots SnapshotBuilder
		executors ApplyExecutorFactory
		recovery  RecoveryExecutorFactory
	}{
		{
			name: "snapshot builder", executors: &fakeApplyExecutorFactory{},
			recovery: readyRecoveryFactory(),
		},
		{
			name: "executor factory", snapshots: &fakeSnapshotBuilder{},
			recovery: readyRecoveryFactory(),
		},
		{
			name: "recovery factory", snapshots: &fakeSnapshotBuilder{},
			executors: &fakeApplyExecutorFactory{},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := New(
				test.snapshots,
				test.executors,
				test.recovery,
			); err == nil {
				t.Fatal("New() accepted a missing dependency")
			}
		})
	}
}

func TestReviewBuildsOneImmutablePlan(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	factory := &fakeApplyExecutorFactory{}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()

	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	request.Components[0] = domain.ComponentCodex
	request.MCPSelections[0].Adapters[0] = domain.ComponentCodex
	request.MCPSelections = nil

	gotRequest := reviewed.Request()
	if !reflect.DeepEqual(gotRequest, testRequest()) {
		t.Fatalf("Request() = %#v, want %#v", gotRequest, testRequest())
	}
	gotRequest.MCPSelections[0].Adapters[0] = domain.ComponentOpenCode
	if !reflect.DeepEqual(reviewed.Request(), testRequest()) {
		t.Fatal("Request() exposed mutable nested state")
	}
	executable := reviewed.Executable()
	if executable.Release != testReleaseIdentity() {
		t.Fatalf("release = %#v", executable.Release)
	}
	if !reflect.DeepEqual(executable.Desired, testRequest().Components) {
		t.Fatalf("desired = %#v", executable.Desired)
	}
	if len(executable.Plan.Operations) != 1 ||
		executable.Plan.Operations[0].Kind != domain.OperationInstall {
		t.Fatalf("filesystem plan = %#v", executable.Plan)
	}
	if len(reviewed.Semantic().Filesystem.Operations) != 1 {
		t.Fatalf("semantic plan = %#v", reviewed.Semantic())
	}
	if builder.builds != 1 {
		t.Fatalf("snapshot builds = %d, want 1", builder.builds)
	}
	if factory.opens != 0 {
		t.Fatalf("executor factory opens = %d, want 0", factory.opens)
	}
}

func TestReviewFailureDoesNotOpenApplyResources(t *testing.T) {
	snapshotErr := errors.New("snapshot failed")
	builder := &fakeSnapshotBuilder{errors: []error{snapshotErr}}
	factory := &fakeApplyExecutorFactory{}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	if _, err := service.Review(testRequest()); !errors.Is(err, snapshotErr) {
		t.Fatalf("Review() error = %v", err)
	}
	if factory.opens != 0 {
		t.Fatalf("executor factory opens = %d, want 0", factory.opens)
	}
}

func TestReviewRejectsConfiguredDiagnosticsBeforeOpeningApplyResources(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	factory := &fakeApplyExecutorFactory{}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()
	request.Diagnostics = diagnostics.Desired{Configured: true, Events: true}

	_, err = service.Review(request)
	if err == nil || !strings.Contains(err.Error(),
		"configured diagnostics are not executable and cannot be prepared") {
		t.Fatalf("Review() error = %v", err)
	}
	if factory.opens != 0 {
		t.Fatalf("executor factory opens = %d, want 0", factory.opens)
	}
}

func TestRequestAndSemanticClonesPreserveDiagnostics(t *testing.T) {
	desired := diagnostics.Desired{Configured: true, Events: true, Feedback: true}
	request := Request{Diagnostics: desired}
	if got := cloneRequest(request).Diagnostics; got != desired {
		t.Fatalf("cloneRequest().Diagnostics = %#v, want %#v", got, desired)
	}
	original := lifecycle.Preview{Diagnostics: diagnostics.Plan{Intents: []diagnostics.Intent{{
		ComponentID: domain.ComponentClaudeCode,
		Events:      true,
	}}}}
	cloned := cloneSemantic(original)
	cloned.Diagnostics.Intents[0].Events = false
	if !original.Diagnostics.Intents[0].Events {
		t.Fatal("cloneSemantic() exposed diagnostics intent storage")
	}
}

func TestReviewIsolatesRequestFromSnapshotBuilderMutation(t *testing.T) {
	request := testRequest()
	original := cloneRequest(request)
	builder := &fakeSnapshotBuilder{
		snapshots: []Snapshot{testSnapshot(t)},
		mutateRequest: func(candidate *Request) {
			candidate.Components[0] = domain.ComponentCodex
			candidate.MCPSelections[0].Adapters[0] = domain.ComponentCodex
		},
	}
	service, err := New(builder, &fakeApplyExecutorFactory{}, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if !reflect.DeepEqual(reviewed.Request(), original) {
		t.Fatalf("reviewed request = %#v, want %#v", reviewed.Request(), original)
	}
	if !reflect.DeepEqual(builder.requests, []Request{original}) {
		t.Fatalf("snapshot requests = %#v, want %#v", builder.requests, []Request{original})
	}
}

func TestRequestRefresherPreservesDiagnosticsDesiredState(t *testing.T) {
	request := testRequest()
	request.Diagnostics = diagnostics.Desired{Events: true}
	refresher := requestRefresher{
		snapshots: &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}},
		request:   request,
	}

	_, err := refresher.Refresh(request.Components)
	if err == nil || !strings.Contains(err.Error(), "plan diagnostics: diagnostics features require") {
		t.Fatalf("Refresh() error = %v", err)
	}
}

func TestApplyRefreshesTheCompleteReviewedRequestAndClosesSession(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{
		testSnapshot(t),
		testSnapshot(t),
	}}
	session := &fakeApplySession{refresh: true}
	factory := &fakeApplyExecutorFactory{session: session}
	service, err := New(builder, factory, readyRecoveryFactory())
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
	if len(result.Warnings) != 0 {
		t.Fatalf("warnings = %#v", result.Warnings)
	}
	if builder.builds != 2 {
		t.Fatalf("snapshot builds = %d, want 2", builder.builds)
	}
	wantRequests := []Request{testRequest(), testRequest()}
	if !reflect.DeepEqual(builder.requests, wantRequests) {
		t.Fatalf("snapshot requests = %#v, want %#v", builder.requests, wantRequests)
	}
	if factory.opens != 1 || session.applies != 1 || session.closes != 1 {
		t.Fatalf(
			"opens/applies/closes = %d/%d/%d",
			factory.opens, session.applies, session.closes,
		)
	}
	if !reflect.DeepEqual(session.fresh, reviewed.Executable()) {
		t.Fatalf("fresh preview = %#v, want %#v", session.fresh, reviewed.Executable())
	}
}

func TestApplyReportsExecutorFactoryFailures(t *testing.T) {
	openErr := errors.New("open failed")
	tests := []struct {
		name    string
		factory *fakeApplyExecutorFactory
	}{
		{name: "open error", factory: &fakeApplyExecutorFactory{err: openErr}},
		{name: "nil session", factory: &fakeApplyExecutorFactory{}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
			service, err := New(builder, test.factory, readyRecoveryFactory())
			if err != nil {
				t.Fatalf("New() error = %v", err)
			}
			reviewed, err := service.Review(testRequest())
			if err != nil {
				t.Fatalf("Review() error = %v", err)
			}

			if _, err := service.Apply(reviewed); err == nil {
				t.Fatal("Apply() accepted an unavailable executor")
			}
			if test.factory.opens != 1 {
				t.Fatalf("factory opens = %d, want 1", test.factory.opens)
			}
		})
	}
}

func TestApplyClosesSessionWhenRefreshFails(t *testing.T) {
	refreshErr := errors.New("refresh failed")
	builder := &fakeSnapshotBuilder{
		snapshots: []Snapshot{testSnapshot(t)},
		errors:    []error{nil, refreshErr},
	}
	session := &fakeApplySession{refresh: true}
	factory := &fakeApplyExecutorFactory{session: session}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.Apply(reviewed); !errors.Is(err, refreshErr) {
		t.Fatalf("Apply() error = %v", err)
	}
	if builder.builds != 2 || session.closes != 1 {
		t.Fatalf("builds/closes = %d/%d, want 2/1", builder.builds, session.closes)
	}
}

func TestApplyRejectsRefresherComponentMismatchAndStillCloses(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	session := &fakeApplySession{
		refresh:        true,
		refreshDesired: []domain.ComponentID{domain.ComponentCodex},
	}
	factory := &fakeApplyExecutorFactory{session: session}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.Apply(reviewed); err == nil ||
		!strings.Contains(err.Error(), "reviewed component selection") {
		t.Fatalf("Apply() error = %v", err)
	}
	if builder.builds != 1 {
		t.Fatalf("snapshot builds = %d, want 1", builder.builds)
	}
	if session.closes != 1 {
		t.Fatalf("session closes = %d, want 1", session.closes)
	}
}

func TestApplyRejectsAChangedFreshSnapshotAndStillCloses(t *testing.T) {
	changed := testSnapshot(t)
	changed.Release.ID = "release-v2"
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{
		testSnapshot(t),
		changed,
	}}
	session := &fakeApplySession{refresh: true}
	factory := &fakeApplyExecutorFactory{session: session}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.Apply(reviewed); err == nil ||
		!strings.Contains(err.Error(), "preview changed") {
		t.Fatalf("Apply() error = %v", err)
	}
	if builder.builds != 2 || session.closes != 1 {
		t.Fatalf("builds/closes = %d/%d, want 2/1", builder.builds, session.closes)
	}
}

func TestApplyReportsSessionCloseFailure(t *testing.T) {
	closeErr := errors.New("close failed")
	applyErr := errors.New("apply failed")
	tests := []struct {
		name      string
		applyErr  error
		wantError bool
	}{
		{name: "successful apply becomes a warning"},
		{name: "failed apply joins the close failure", applyErr: applyErr, wantError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
			session := &fakeApplySession{applyErr: test.applyErr, closeErr: closeErr}
			factory := &fakeApplyExecutorFactory{session: session}
			service, err := New(builder, factory, readyRecoveryFactory())
			if err != nil {
				t.Fatalf("New() error = %v", err)
			}
			reviewed, err := service.Review(testRequest())
			if err != nil {
				t.Fatalf("Review() error = %v", err)
			}

			result, err := service.Apply(reviewed)
			if test.wantError {
				if !errors.Is(err, applyErr) || !errors.Is(err, closeErr) {
					t.Fatalf("Apply() error = %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("Apply() error = %v", err)
			}
			if len(result.Warnings) != 1 ||
				!strings.Contains(result.Warnings[0], closeErr.Error()) {
				t.Fatalf("warnings = %#v", result.Warnings)
			}
		})
	}
}

func TestApplyRejectsAnUnreviewedPlanBeforeOpeningResources(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	factory := &fakeApplyExecutorFactory{}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	if _, err := service.Apply(ReviewedPlan{}); err == nil ||
		!strings.Contains(err.Error(), "not produced by Review") {
		t.Fatalf("Apply() error = %v", err)
	}
	if builder.builds != 0 || factory.opens != 0 {
		t.Fatalf("builds/opens = %d/%d, want 0/0", builder.builds, factory.opens)
	}
}
