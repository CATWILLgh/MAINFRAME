package configuration_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectMapsExternalStateWithoutReadingTarget(t *testing.T) {
	tests := map[string]struct {
		external configuration.ExternalStatus
		status   configuration.Status
		reason   configuration.Reason
	}{
		"satisfied": {
			external: configuration.ExternalSatisfied,
			status:   configuration.Ready,
			reason:   configuration.ExternalStateSatisfied,
		},
		"action required": {
			external: configuration.ExternalActionRequired,
			status:   configuration.NeedsChange,
			reason:   configuration.ManualActionRequired,
		},
		"unavailable": {
			external: configuration.ExternalUnavailable,
			status:   configuration.NotAssessed,
			reason:   configuration.ExternalStateUnavailable,
		},
		"failed": {
			external: configuration.ExternalFailed,
			status:   configuration.Attention,
			reason:   configuration.ExternalInspectionFailed,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			host := &fakeHost{}
			external := fakeExternalObserver{status: test.external}
			inspection, err := configuration.InspectWithExternal(
				[]releasecontract.Resource{externalResource()},
				host,
				external,
			)
			if err != nil {
				t.Fatalf("InspectWithExternal() error = %v", err)
			}
			want := configuration.Observation{
				ResourceID:  "trust",
				ComponentID: domain.ComponentCodex,
				Status:      test.status,
				Reason:      test.reason,
			}
			if got := inspection.Observations()[0]; !reflect.DeepEqual(got, want) {
				t.Fatalf("observation = %#v, want %#v", got, want)
			}
			if len(host.calls) != 0 {
				t.Fatalf("manual action read filesystem target: %#v", host.calls)
			}
		})
	}
}

func TestExternalStatePlansManualActionsAndNoticesWithoutBlockingPreparation(t *testing.T) {
	tests := map[string]struct {
		status        configuration.ExternalStatus
		selected      bool
		manualActions int
		notices       int
	}{
		"required selected": {
			status: configuration.ExternalActionRequired, selected: true, manualActions: 1,
		},
		"unavailable selected": {
			status: configuration.ExternalUnavailable, selected: true, notices: 1,
		},
		"failed selected": {
			status: configuration.ExternalFailed, selected: true, notices: 1,
		},
		"required deselected": {
			status: configuration.ExternalActionRequired,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			inspection, err := configuration.InspectWithExternal(
				[]releasecontract.Resource{externalResource()},
				&fakeHost{},
				fakeExternalObserver{status: test.status},
			)
			if err != nil {
				t.Fatalf("InspectWithExternal() error = %v", err)
			}
			var included []domain.ComponentID
			if test.selected {
				included = []domain.ComponentID{domain.ComponentCodex}
			}
			plan, err := inspection.Plan(included)
			if err != nil {
				t.Fatalf("Plan() error = %v", err)
			}
			if len(plan.ManualActions) != test.manualActions ||
				len(plan.Notices) != test.notices ||
				len(plan.Changes) != 0 ||
				len(plan.Issues) != 0 {
				t.Fatalf("plan = %#v", plan)
			}
			prepared, err := inspection.Prepare(included)
			if err != nil {
				t.Fatalf("Prepare() error = %v", err)
			}
			if len(prepared.Transitions()) != 0 {
				t.Fatalf("manual state produced transitions: %#v", prepared.Transitions())
			}
		})
	}
}

type fakeExternalObserver struct {
	status configuration.ExternalStatus
}

func (observer fakeExternalObserver) Observe(
	releasecontract.Resource,
) configuration.ExternalObservation {
	return configuration.ExternalObservation{Status: observer.status}
}

func externalResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "trust",
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
