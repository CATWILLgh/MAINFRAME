package application

import (
	"errors"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type fakeSnapshotBuilder struct {
	snapshots     []Snapshot
	errors        []error
	requests      []Request
	mutateRequest func(*Request)
	builds        int
}

func (builder *fakeSnapshotBuilder) Build(request Request) (Snapshot, error) {
	index := builder.builds
	builder.builds++
	builder.requests = append(builder.requests, cloneRequest(request))
	if builder.mutateRequest != nil {
		builder.mutateRequest(&request)
	}
	if index < len(builder.errors) && builder.errors[index] != nil {
		return Snapshot{}, builder.errors[index]
	}
	if index >= len(builder.snapshots) {
		return Snapshot{}, errors.New("unexpected snapshot build")
	}
	return builder.snapshots[index], nil
}

type fakeApplyExecutorFactory struct {
	session ApplySession
	opens   int
	err     error
	events  *[]string
}

func (factory *fakeApplyExecutorFactory) Open(refresher executor.Refresher) (ApplySession, error) {
	factory.opens++
	appendEvent(factory.events, "open apply")
	if factory.err != nil {
		return nil, factory.err
	}
	session, ok := factory.session.(*fakeApplySession)
	if ok {
		session.refresher = refresher
	}
	return factory.session, nil
}

type fakeApplySession struct {
	refresher      executor.Refresher
	refresh        bool
	refreshDesired []domain.ComponentID
	fresh          executor.Preview
	applies        int
	closes         int
	applyErr       error
	closeErr       error
	result         executor.Result
	events         *[]string
}

func (session *fakeApplySession) Apply(preview executor.Preview) (executor.Result, error) {
	session.applies++
	appendEvent(session.events, "apply")
	if session.refresh {
		desired := preview.Desired
		if session.refreshDesired != nil {
			desired = session.refreshDesired
		}
		fresh, err := session.refresher.Refresh(desired)
		if err != nil {
			return executor.Result{}, err
		}
		session.fresh = fresh
		if !reflect.DeepEqual(preview, fresh) {
			return executor.Result{}, errors.New("preview changed")
		}
	}
	return session.result, session.applyErr
}

func (session *fakeApplySession) Close() error {
	session.closes++
	appendEvent(session.events, "close apply")
	return session.closeErr
}

type fakeRecoveryExecutorFactory struct {
	session RecoverySession
	opens   int
	err     error
	events  *[]string
}

func (factory *fakeRecoveryExecutorFactory) Open() (RecoverySession, error) {
	factory.opens++
	appendEvent(factory.events, "open recovery")
	return factory.session, factory.err
}

type fakeRecoverySession struct {
	result     executor.Result
	recovers   int
	closes     int
	recoverErr error
	closeErr   error
	events     *[]string
}

func (session *fakeRecoverySession) Recover() (executor.Result, error) {
	session.recovers++
	appendEvent(session.events, "recover")
	return session.result, session.recoverErr
}

func (session *fakeRecoverySession) Close() error {
	session.closes++
	appendEvent(session.events, "close recovery")
	return session.closeErr
}

func readyRecoveryFactory() RecoveryExecutorFactory {
	return &fakeRecoveryExecutorFactory{session: &fakeRecoverySession{}}
}

func appendEvent(events *[]string, event string) {
	if events != nil {
		*events = append(*events, event)
	}
}

func testRequest() Request {
	return Request{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID:  "context7",
			ProfileID: "remote-api-key",
			Adapters:  []domain.ComponentID{domain.ComponentClaudeCode},
		}},
	}
}

func testSnapshot(t *testing.T) Snapshot {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{{
				Target: domain.Location{
					Root: domain.RootClaudeConfig,
					Path: "CLAUDE.md",
				},
				SourcePath: "claude-code/CLAUDE.md",
			}},
		},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
		{ID: domain.ComponentCodexGates},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	service, err := lifecycle.New(model, domain.ObservedState{})
	if err != nil {
		t.Fatalf("lifecycle.New() error = %v", err)
	}
	return Snapshot{Release: testReleaseIdentity(), Lifecycle: service}
}

func testReleaseIdentity() executor.ReleaseIdentity {
	return executor.ReleaseIdentity{ID: "release-v1", IndexSHA256: testReleaseDigest}
}
