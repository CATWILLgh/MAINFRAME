package lifecycle

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestAntigravityTargetReportsFilesystemAndExternalValidationSeparately(t *testing.T) {
	model := antigravityModel(t)
	resource := antigravityValidationResource()
	tests := []struct {
		name     string
		observed domain.ObservedState
		status   TargetStatus
		selected bool
	}{
		{name: "absent", status: StatusAbsent},
		{
			name:     "managed",
			observed: antigravityObserved(domain.OwnershipManagedExact),
			status:   StatusManaged, selected: true,
		},
		{
			name:     "drifted",
			observed: antigravityObserved(domain.OwnershipManagedDrifted),
			status:   StatusAttention, selected: true,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			service, err := NewWithResources(model, test.observed, []releasecontract.Resource{resource})
			if err != nil {
				t.Fatalf("service: %v", err)
			}
			target := service.Targets()[3]
			assertAntigravityTarget(t, target, test.status, test.selected)
		})
	}
}

func antigravityModel(t *testing.T) installmodel.Model {
	t.Helper()
	components := []installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{
			ID: domain.ComponentAntigravity2,
			Artifacts: []installmodel.ArtifactSpec{{
				Target: domain.Location{
					Root: domain.RootAntigravityConfig,
					Path: "plugins/mainframe",
				},
				SourcePath: "bundles/antigravity-2/plugin",
			}},
		},
	}
	model, err := installmodel.New(components)
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	return model
}

func antigravityValidationResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "antigravity-2.live-activation",
		ComponentID: domain.ComponentAntigravity2,
		Strategy:    releasecontract.StrategyManualAction,
		Target: domain.Location{
			Root: domain.RootAntigravityConfig,
			Path: "plugins/mainframe",
		},
		Observation: releasecontract.SupportUnimplemented,
		Apply:       releasecontract.SupportUnimplemented,
	}
}

func assertAntigravityTarget(
	t *testing.T,
	target Target,
	status TargetStatus,
	selected bool,
) {
	t.Helper()
	if target.ID != domain.ComponentAntigravity2 ||
		target.Status != status ||
		target.Selected != selected {
		t.Fatalf("target = %#v", target)
	}
	if len(target.Configuration) != 1 ||
		target.Configuration[0].Status != ConfigurationNotAssessed ||
		target.Configuration[0].Reason != ConfigurationObservationUnsupported {
		t.Fatalf("configuration = %#v", target.Configuration)
	}
}

func antigravityObserved(ownership domain.OwnershipStatus) domain.ObservedState {
	return domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentAntigravity2,
			Artifacts: []domain.Artifact{
				{
					Location: domain.Location{
						Root: domain.RootAntigravityConfig,
						Path: "plugins/mainframe",
					},
					Ownership: ownership,
				},
			},
		},
	}}
}
