package hostcompatibility

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type applicationEvaluationCase struct {
	name      string
	inventory ApplicationInventory
	want      Status
	detected  []string
}

func TestEvaluateApplicationRequirements(t *testing.T) {
	component := domain.ComponentID("antigravity")
	requirement := releasecontract.HostRequirement{
		ComponentID:      component,
		Kind:             releasecontract.HostRequirementDarwinApplicationBundleV1,
		BundleIdentifier: "com.google.antigravity",
		ExactVersions:    []string{"2.2.1", "2.2.0"},
	}

	for _, test := range applicationEvaluationCases() {
		t.Run(test.name, func(t *testing.T) {
			got := Evaluate([]releasecontract.HostRequirement{requirement}, test.inventory)
			if len(got) != 1 || got[0].Status != test.want {
				t.Fatalf("assessment = %#v, want status %q", got, test.want)
			}
			if !reflect.DeepEqual(got[0].DetectedVersions, test.detected) {
				t.Fatalf("detected versions = %#v, want %#v", got[0].DetectedVersions, test.detected)
			}
			if !reflect.DeepEqual(got[0].ExpectedVersions, []string{"2.2.0", "2.2.1"}) {
				t.Fatalf("expected versions = %#v", got[0].ExpectedVersions)
			}
		})
	}
}

func applicationEvaluationCases() []applicationEvaluationCase {
	return []applicationEvaluationCase{
		{
			name: "satisfied exact version",
			inventory: ApplicationInventory{Available: true, Complete: true, Applications: []Application{
				{BundleIdentifier: "com.google.antigravity", Version: "2.2.1"},
			}},
			want: StatusSatisfied, detected: []string{"2.2.1"},
		},
		{
			name:      "missing application",
			inventory: ApplicationInventory{Available: true, Complete: true},
			want:      StatusMissing,
		},
		{
			name: "unsupported installed version",
			inventory: ApplicationInventory{Available: true, Complete: true, Applications: []Application{
				{BundleIdentifier: "com.google.antigravity", Version: "2.1.0"},
			}},
			want: StatusIncompatible, detected: []string{"2.1.0"},
		},
		{
			name:      "incomplete inventory cannot prove missing",
			inventory: ApplicationInventory{Available: true, Complete: false},
			want:      StatusUnavailable,
		},
		{
			name: "exact match wins over incomplete scan",
			inventory: ApplicationInventory{Available: true, Complete: false, Applications: []Application{
				{BundleIdentifier: "com.google.antigravity", Version: "2.2.1"},
			}},
			want: StatusSatisfied, detected: []string{"2.2.1"},
		},
		{
			name: "unsupported duplicate makes an exact match ambiguous",
			inventory: ApplicationInventory{Available: true, Complete: true, Applications: []Application{
				{BundleIdentifier: "com.google.antigravity", Version: "2.2.1"},
				{BundleIdentifier: "com.google.antigravity", Version: "2.1.0"},
			}},
			want: StatusIncompatible, detected: []string{"2.1.0", "2.2.1"},
		},
		{
			name:      "unavailable platform",
			inventory: ApplicationInventory{},
			want:      StatusUnavailable,
		},
	}
}

func TestEvaluateRequiresEveryRowAndReturnsStableClonedResults(t *testing.T) {
	componentA := domain.ComponentID("a")
	componentB := domain.ComponentID("b")
	requirements := []releasecontract.HostRequirement{
		{ComponentID: componentB, Kind: releasecontract.HostRequirementDarwinApplicationBundleV1, BundleIdentifier: "app.b", ExactVersions: []string{"1"}},
		{ComponentID: componentA, Kind: releasecontract.HostRequirementDarwinApplicationBundleV1, BundleIdentifier: "app.a2", ExactVersions: []string{"2"}},
		{ComponentID: componentA, Kind: releasecontract.HostRequirementDarwinApplicationBundleV1, BundleIdentifier: "app.a1", ExactVersions: []string{"1"}},
	}
	inventory := ApplicationInventory{Available: true, Complete: true, Applications: []Application{
		{BundleIdentifier: "app.a1", Version: "1"},
		{BundleIdentifier: "app.a2", Version: "old"},
		{BundleIdentifier: "app.b", Version: "1"},
	}}

	got := Evaluate(requirements, inventory)
	want := []Assessment{
		{ComponentID: componentA, Status: StatusIncompatible, DetectedVersions: []string{"old"}, ExpectedVersions: []string{"1", "2"}},
		{ComponentID: componentB, Status: StatusSatisfied, DetectedVersions: []string{"1"}, ExpectedVersions: []string{"1"}},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("assessments = %#v, want %#v", got, want)
	}

	requirements[0].ExactVersions[0] = "changed"
	inventory.Applications[0].Version = "changed"
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("assessment aliases caller input: %#v", got)
	}
}

func TestEvaluateTreatsUnknownRequirementKindAsUnavailable(t *testing.T) {
	got := Evaluate([]releasecontract.HostRequirement{{
		ComponentID: domain.ComponentID("future"), Kind: releasecontract.HostRequirementKind("future-kind"),
	}}, ApplicationInventory{Available: true, Complete: true})
	if len(got) != 1 || got[0].Status != StatusUnavailable {
		t.Fatalf("assessment = %#v", got)
	}
}
