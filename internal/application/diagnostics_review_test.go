package application

import (
	"io/fs"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestReviewRejectsConfiguredDiagnosticsWithoutScopedResources(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	factory := &fakeApplyExecutorFactory{}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()
	request.Diagnostics = diagnostics.Desired{Configured: true, Events: true}

	_, err = service.Review(request)
	if err == nil || !strings.Contains(
		err.Error(),
		"scoped diagnostics resource is unavailable",
	) {
		t.Fatalf("Review() error = %v", err)
	}
	if factory.opens != 0 {
		t.Fatalf("executor factory opens = %d, want 0", factory.opens)
	}
}

func TestReviewCarriesScopedDiagnosticsIntoExecutableConfiguration(t *testing.T) {
	tests := []struct {
		name        string
		current     []byte
		desired     diagnostics.Desired
		wantPresent bool
	}{
		{
			name: "enable feedback",
			desired: diagnostics.Desired{
				Configured: true,
				Events:     true,
				Feedback:   true,
			},
			wantPresent: true,
		},
		{
			name: "explicitly disable diagnostics",
			current: []byte(
				`{"events":true,"feedback":false,"schema_version":1}`,
			),
			desired: diagnostics.Desired{Configured: true},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			snapshot := applicationDiagnosticsSnapshot(t, test.current)
			builder := &fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}}
			factory := &fakeApplyExecutorFactory{}
			service, err := New(builder, factory, readyRecoveryFactory())
			if err != nil {
				t.Fatalf("New() error = %v", err)
			}
			request := Request{
				Components:  []domain.ComponentID{domain.ComponentClaudeCode},
				Diagnostics: test.desired,
			}

			reviewed, err := service.Review(request)
			if err != nil {
				t.Fatalf("Review() error = %v", err)
			}
			if !reviewed.Semantic().Diagnostics.Executable {
				t.Fatal("reviewed diagnostics remained non-executable")
			}
			transitions := reviewed.Executable().Configuration.Transitions()
			if len(transitions) != 1 ||
				transitions[0].ResourceIDs[0] != "claude-code.diagnostics" ||
				transitions[0].Mutations[0].After.Exists != test.wantPresent {
				t.Fatalf("configuration transitions = %#v", transitions)
			}
			if test.wantPresent && !strings.Contains(
				string(transitions[0].Mutations[0].After.Content),
				`"feedback": true`,
			) {
				t.Fatalf("configuration transitions = %#v", transitions)
			}
			if factory.opens != 0 {
				t.Fatalf("Review() opened executor resources: %d", factory.opens)
			}
		})
	}
}

func applicationDiagnosticsSnapshot(t *testing.T, current []byte) Snapshot {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{{
				UnitID: "claude-code.dev.harness-feedback",
				Target: domain.Location{
					Root: domain.RootClaudeConfig,
					Path: "skills/mainframe-dev",
				},
				SourcePath: "dev/harness-feedback-plugin",
				Feature:    domain.FeatureHarnessFeedback,
			}},
		},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	resource := releasecontract.Resource{
		ID:          "claude-code.diagnostics",
		ComponentID: domain.ComponentClaudeCode,
		Strategy:    releasecontract.StrategyExactJSONDocument,
		SourcePath:  "bundles/claude-code/diagnostics.json",
		Target: domain.Location{
			Root: domain.RootClaudeConfig,
			Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
	host := applicationDiagnosticsHost{}
	if current != nil {
		host[resource.Target] = hostfs.Entry{
			Kind:    hostfs.EntryRegular,
			Content: append([]byte(nil), current...),
			Mode:    0o600,
			Device:  1,
			Inode:   77,
		}
	}
	inspection, err := configuration.Inspect([]releasecontract.Resource{resource}, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	lifecycleService, err := lifecycle.NewWithInspection(
		model,
		domain.ObservedState{},
		inspection,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspection() error = %v", err)
	}
	return Snapshot{
		Release:   testReleaseIdentity(),
		Lifecycle: lifecycleService,
	}
}

type applicationDiagnosticsHost map[domain.Location]hostfs.Entry

func (h applicationDiagnosticsHost) Inspect(
	location domain.Location,
	_ bool,
) (hostfs.Entry, error) {
	if entry, ok := h[location]; ok {
		return entry, nil
	}
	return hostfs.Entry{}, fs.ErrNotExist
}
