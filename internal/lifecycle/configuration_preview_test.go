package lifecycle

import (
	"io/fs"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPreviewPlansConfigurationForDeduplicatedDependencyClosure(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode, Dependencies: []domain.ComponentID{"shared"}},
		{ID: domain.ComponentCodex, Dependencies: []domain.ComponentID{"shared"}},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
		{ID: "shared"},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	resource := releasecontract.Resource{
		ID: "shared.credentials", ComponentID: "shared",
		Strategy:    releasecontract.StrategySeedIfAbsent,
		Target:      domain.Location{Root: domain.RootHome, Path: ".credentials"},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
	}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		previewHost{},
	)
	if err != nil {
		t.Fatalf("inspect: %v", err)
	}
	service, err := NewWithInspection(model, domain.ObservedState{}, inspection)
	if err != nil {
		t.Fatalf("service: %v", err)
	}

	got, err := service.Preview([]domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentCodex,
	})
	if err != nil {
		t.Fatalf("preview: %v", err)
	}
	want := []configuration.Change{
		{
			ResourceID:  "shared.credentials",
			ComponentID: "shared",
			Kind:        configuration.ChangeAdd,
		},
	}
	if !reflect.DeepEqual(got.Configuration.Changes, want) {
		t.Fatalf("configuration changes = %#v, want %#v", got.Configuration.Changes, want)
	}
}

func TestLegacyPreviewReportsConfigurationPlanningUnavailable(t *testing.T) {
	resource := releasecontract.Resource{
		ID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Observation: releasecontract.SupportUnimplemented,
		Apply:       releasecontract.SupportUnimplemented,
	}
	service, err := NewWithResources(
		testModel(t),
		domain.ObservedState{},
		[]releasecontract.Resource{resource},
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}

	got, err := service.Preview([]domain.ComponentID{domain.ComponentOpenCode})
	if err != nil {
		t.Fatalf("preview: %v", err)
	}
	want := []configuration.Issue{
		{
			ResourceID:  "opencode.permissions",
			ComponentID: domain.ComponentOpenCode,
			Kind:        configuration.IssuePlanningUnavailable,
			Reason:      configuration.ObservationUnsupported,
		},
	}
	if len(got.Configuration.Changes) != 0 {
		t.Fatalf("legacy preview fabricated changes: %#v", got.Configuration.Changes)
	}
	if !reflect.DeepEqual(got.Configuration.Issues, want) {
		t.Fatalf("configuration issues = %#v, want %#v", got.Configuration.Issues, want)
	}
}

func TestLegacyObservedConfigurationStillReportsPlanningUnavailable(t *testing.T) {
	resource := releasecontract.Resource{
		ID: "codex.credentials", ComponentID: domain.ComponentCodex,
		Strategy:    releasecontract.StrategySeedIfAbsent,
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
	}
	service, err := NewWithConfiguration(
		testModel(t),
		domain.ObservedState{},
		[]releasecontract.Resource{resource},
		[]configuration.Observation{
			{
				ResourceID:  resource.ID,
				ComponentID: resource.ComponentID,
				Status:      configuration.NeedsChange,
				Reason:      configuration.ResourceMissing,
			},
		},
	)
	if err != nil {
		t.Fatalf("service: %v", err)
	}

	got, err := service.Preview([]domain.ComponentID{domain.ComponentCodex})
	if err != nil {
		t.Fatalf("preview: %v", err)
	}
	want := configuration.Issue{
		ResourceID:  resource.ID,
		ComponentID: resource.ComponentID,
		Kind:        configuration.IssuePlanningUnavailable,
		Reason:      configuration.ResourceMissing,
	}
	if len(got.Configuration.Changes) != 0 ||
		!reflect.DeepEqual(got.Configuration.Issues, []configuration.Issue{want}) {
		t.Fatalf("legacy configuration plan = %#v, want issue %#v", got.Configuration, want)
	}
}

func TestPreviewRejectsInvalidSelectionBeforeConfigurationPlanning(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})

	_, err := service.Preview([]domain.ComponentID{
		domain.ComponentCodex,
		domain.ComponentCodex,
	})
	if err == nil || !strings.Contains(err.Error(), "duplicate") {
		t.Fatalf("Preview() error = %v, want duplicate selection error", err)
	}
}

type previewHost map[domain.Location]hostfs.Entry

func (host previewHost) Inspect(
	location domain.Location,
	_ bool,
) (hostfs.Entry, error) {
	entry, exists := host[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	return entry, nil
}
