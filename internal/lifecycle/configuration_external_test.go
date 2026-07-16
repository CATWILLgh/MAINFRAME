package lifecycle

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPreviewRequiresHookReviewUntilDesiredHookArtifactIsManagedExact(t *testing.T) {
	model := externalLifecycleModel(t)
	resource := externalLifecycleResource()
	inspection, err := configuration.InspectWithExternal(
		[]releasecontract.Resource{resource},
		externalLifecycleHost{},
		externalLifecycleObserver{},
	)
	if err != nil {
		t.Fatalf("InspectWithExternal() error = %v", err)
	}
	tests := map[string]struct {
		observed domain.ObservedState
		want     []configuration.ManualAction
	}{
		"artifact absent": {
			want: []configuration.ManualAction{{
				ResourceID:  resource.ID,
				ComponentID: domain.ComponentCodex,
				Kind:        configuration.ManualActionCodexHookTrust,
				Reason:      configuration.ManualActionRequired,
			}},
		},
		"artifact managed exact": {
			observed: domain.ObservedState{Components: []domain.ObservedComponent{{
				ID: domain.ComponentCodex,
				Artifacts: []domain.Artifact{{
					Location:  resource.Target,
					Ownership: domain.OwnershipManagedExact,
				}},
			}}},
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			assertExternalLifecyclePreview(
				t, model, inspection, test.observed, test.want,
			)
		})
	}
}

func assertExternalLifecyclePreview(
	t *testing.T,
	model installmodel.Model,
	inspection configuration.Inspection,
	observed domain.ObservedState,
	wantActions []configuration.ManualAction,
) {
	t.Helper()
	service, err := NewWithInspection(model, observed, inspection)
	if err != nil {
		t.Fatalf("NewWithInspection() error = %v", err)
	}
	wantStatus := configuration.NeedsChange
	if len(wantActions) == 0 {
		wantStatus = configuration.Ready
	}
	for _, target := range service.Targets() {
		if target.ID == domain.ComponentCodex &&
			target.Configuration[0].Status != wantStatus {
			t.Fatalf(
				"configuration status = %q, want %q",
				target.Configuration[0].Status,
				wantStatus,
			)
		}
	}
	preview, err := service.Preview([]domain.ComponentID{domain.ComponentCodex})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if !reflect.DeepEqual(preview.Configuration.ManualActions, wantActions) {
		t.Fatalf(
			"manual actions = %#v, want %#v",
			preview.Configuration.ManualActions,
			wantActions,
		)
	}
}

func externalLifecycleModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{{
				Target:     externalLifecycleResource().Target,
				SourcePath: "bundles/codex/hooks.json",
			}},
		},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("install model: %v", err)
	}
	return model
}

func externalLifecycleResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "codex.hook-trust",
		ComponentID: domain.ComponentCodex,
		Strategy:    releasecontract.StrategyManualAction,
		SourcePath:  "bundles/codex/hooks.json",
		Target: domain.Location{
			Root: domain.RootCodexConfig,
			Path: "hooks.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		ExternalState: &releasecontract.ExternalStateDescriptor{
			Kind: releasecontract.ExternalStateCodexHookTrust,
		},
	}
}

type externalLifecycleHost struct{}

func (externalLifecycleHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	panic("external state must not inspect filesystem")
}

type externalLifecycleObserver struct{}

func (externalLifecycleObserver) Observe(
	releasecontract.Resource,
) configuration.ExternalObservation {
	return configuration.ExternalObservation{
		Status: configuration.ExternalSatisfied,
	}
}
