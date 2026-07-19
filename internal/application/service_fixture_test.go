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
	snapshots []Snapshot
	errors    []error
	builds    int
}

func (builder *fakeSnapshotBuilder) Build() (Snapshot, error) {
	index := builder.builds
	builder.builds++
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
}

func (factory *fakeApplyExecutorFactory) Open(refresher executor.Refresher) (ApplySession, error) {
	factory.opens++
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
}

func (session *fakeApplySession) Apply(preview executor.Preview) (executor.Result, error) {
	session.applies++
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
	return executor.Result{}, session.applyErr
}

func (session *fakeApplySession) Close() error {
	session.closes++
	return session.closeErr
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
