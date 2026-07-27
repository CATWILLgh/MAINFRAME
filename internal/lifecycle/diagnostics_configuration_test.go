package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPreviewPlansScopedExecutableDiagnosticsConfiguration(t *testing.T) {
	claude := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	codex := lifecycleDiagnosticsResource(domain.ComponentCodex)
	service := lifecycleDiagnosticsService(
		t,
		[]releasecontract.Resource{claude, codex},
		nil,
	)

	preview, err := service.Preview(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{
			Configured: true,
			Events:     true,
		},
	})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if !preview.Diagnostics.Executable ||
		len(preview.Configuration.Changes) != 1 ||
		preview.Configuration.Changes[0].ResourceID != claude.ID ||
		preview.Configuration.Changes[0].Kind != configuration.ChangeAdd {
		t.Fatalf("preview = %#v", preview)
	}
}

func TestPrepareConfigurationMapsDiagnosticsDesiredState(t *testing.T) {
	resource := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	tests := []struct {
		name         string
		desired      diagnostics.Desired
		current      []byte
		wantChanges  int
		wantPresent  bool
		wantEvents   bool
		wantFeedback bool
	}{
		{
			name:        "events only",
			desired:     diagnostics.Desired{Configured: true, Events: true},
			wantChanges: 1, wantPresent: true, wantEvents: true,
		},
		{
			name: "feedback inside DEV",
			desired: diagnostics.Desired{
				Configured: true,
				Events:     true,
				Feedback:   true,
			},
			wantChanges: 1, wantPresent: true, wantEvents: true, wantFeedback: true,
		},
		{
			name:        "explicit disable",
			desired:     diagnostics.Desired{Configured: true},
			current:     []byte(resource.ExactJSONExemplar),
			wantChanges: 1,
		},
		{
			name:    "already disabled",
			desired: diagnostics.Desired{Configured: true},
		},
		{
			name:    "unconfigured leaves current untouched",
			current: []byte(resource.ExactJSONExemplar),
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			host := lifecyclePreparationHost{}
			if test.current != nil {
				host[resource.Target] = lifecycleDiagnosticsEntry(test.current)
			}
			service := lifecycleDiagnosticsService(
				t,
				[]releasecontract.Resource{resource},
				host,
			)
			prepared, err := service.PrepareConfiguration(PreviewRequest{
				Components:  []domain.ComponentID{domain.ComponentClaudeCode},
				Diagnostics: test.desired,
			})
			if err != nil {
				t.Fatalf("PrepareConfiguration() error = %v", err)
			}
			transitions := prepared.Transitions()
			if len(transitions) != test.wantChanges {
				t.Fatalf("transitions = %#v", transitions)
			}
			if test.wantChanges == 0 {
				return
			}
			mutation := transitions[0].Mutations[0]
			if mutation.After.Exists != test.wantPresent {
				t.Fatalf("mutation = %#v", mutation)
			}
			if !test.wantPresent {
				return
			}
			content := string(mutation.After.Content)
			if strings.Contains(content, `"events": true`) != test.wantEvents ||
				strings.Contains(content, `"feedback": true`) != test.wantFeedback {
				t.Fatalf("document = %s", content)
			}
		})
	}
}

func TestPrepareDiagnosticsRequiresCompleteScopedResources(t *testing.T) {
	service := lifecycleDiagnosticsService(
		t,
		[]releasecontract.Resource{
			lifecycleDiagnosticsResource(domain.ComponentClaudeCode),
		},
		nil,
	)

	_, err := service.PrepareConfiguration(PreviewRequest{
		Components: []domain.ComponentID{
			domain.ComponentClaudeCode,
			domain.ComponentCodex,
		},
		Diagnostics: diagnostics.Desired{Configured: true, Events: true},
	})
	if err == nil || !strings.Contains(err.Error(), "diagnostics resource") {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
}

func TestDiagnosticsExactDocumentsRejectAmbiguousResources(t *testing.T) {
	resource := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	duplicate := resource
	duplicate.ID = resource.ID + ".duplicate"

	_, _, err := diagnosticsExactDocuments(
		diagnostics.Plan{Intents: []diagnostics.Intent{
			{ComponentID: domain.ComponentClaudeCode, Events: true},
		}},
		[]releasecontract.Resource{resource, duplicate},
	)
	if err == nil || !strings.Contains(err.Error(), "ambiguous") {
		t.Fatalf("diagnosticsExactDocuments() error = %v", err)
	}
}

func TestDiagnosticsExactDocumentsIgnoreOtherExactDocuments(t *testing.T) {
	resource := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	unrelated := resource
	unrelated.ID = "claude-code.other-exact-document"
	unrelated.Target.Path = "mainframe/other.json"

	documents, available, err := diagnosticsExactDocuments(
		diagnostics.Plan{Intents: []diagnostics.Intent{
			{ComponentID: domain.ComponentClaudeCode, Events: true},
		}},
		[]releasecontract.Resource{resource, unrelated},
	)
	if err != nil {
		t.Fatalf("diagnosticsExactDocuments() error = %v", err)
	}
	if !available || len(documents) != 1 ||
		documents[0].ResourceID != resource.ID {
		t.Fatalf("documents = %#v, available = %t", documents, available)
	}
}

func TestMergeConfigurationPlansSortsChangesDeterministically(t *testing.T) {
	got := mergeConfigurationPlans(
		configuration.Plan{Changes: []configuration.Change{
			{
				ResourceID:  "codex.diagnostics",
				ComponentID: domain.ComponentCodex,
				Kind:        configuration.ChangeRemove,
			},
		}},
		configuration.Plan{Changes: []configuration.Change{
			{
				ResourceID:  "claude-code.diagnostics",
				ComponentID: domain.ComponentClaudeCode,
				Kind:        configuration.ChangeAdd,
			},
		}},
	)
	want := []configuration.Change{
		{
			ResourceID:  "claude-code.diagnostics",
			ComponentID: domain.ComponentClaudeCode,
			Kind:        configuration.ChangeAdd,
		},
		{
			ResourceID:  "codex.diagnostics",
			ComponentID: domain.ComponentCodex,
			Kind:        configuration.ChangeRemove,
		},
	}
	if !reflect.DeepEqual(got.Changes, want) {
		t.Fatalf("changes = %#v, want %#v", got.Changes, want)
	}
}

func lifecycleDiagnosticsService(
	t *testing.T,
	resources []releasecontract.Resource,
	host configuration.Host,
) Service {
	t.Helper()
	if host == nil {
		host = lifecyclePreparationHost{}
	}
	inspection, err := configuration.Inspect(resources, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	service, err := NewWithInspection(
		testModel(t),
		domain.ObservedState{},
		inspection,
	)
	if err != nil {
		t.Fatalf("NewWithInspection() error = %v", err)
	}
	return service
}

func lifecycleDiagnosticsResource(
	componentID domain.ComponentID,
) releasecontract.Resource {
	roots := map[domain.ComponentID]domain.RootID{
		domain.ComponentClaudeCode:   domain.RootClaudeConfig,
		domain.ComponentCodex:        domain.RootCodexConfig,
		domain.ComponentOpenCode:     domain.RootOpenCodeConfig,
		domain.ComponentAntigravity2: domain.RootAntigravityData,
	}
	return releasecontract.Resource{
		ID:          string(componentID) + ".diagnostics",
		ComponentID: componentID,
		Strategy:    releasecontract.StrategyExactJSONDocument,
		SourcePath:  "bundles/" + domain.ArtifactPath(componentID) + "/diagnostics.json",
		Target: domain.Location{
			Root: roots[componentID],
			Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
}

func lifecycleDiagnosticsEntry(content []byte) hostfs.Entry {
	return hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: append([]byte(nil), content...),
		Mode: 0o600, Device: 1, Inode: 77,
		BirthSeconds: 78,
	}
}
