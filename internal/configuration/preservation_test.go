package configuration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectionPreservesGenericConfigurationWithoutRemovalIssue(t *testing.T) {
	present := resource(
		"present",
		releasecontract.StrategySeedIfAbsent,
		releasecontract.SupportSupported,
	)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		present.Target: {Kind: hostfs.EntryRegular},
	}}
	inspection, err := configuration.Inspect([]releasecontract.Resource{present}, host)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	got, err := inspection.PlanWithPreservation(nil, []domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if len(got.Changes)+len(got.Issues)+len(got.ManualActions)+len(got.Notices) != 0 {
		t.Fatalf("plan = %#v, want empty", got)
	}
}

func TestInspectionSelectedConfigurationWinsOverPreservation(t *testing.T) {
	inspection := inspectOwnedMap(t, `{"permission":{}}`, `{"version":1,"actions":{}}`, `{"bash":{"*":"allow"}}`)
	components := []domain.ComponentID{"credential-tools"}
	got, err := inspection.PlanWithPreservation(components, components)
	if err != nil {
		t.Fatalf("PlanWithPreservation() error = %v", err)
	}
	if len(got.Changes) != 1 || got.Changes[0].Kind != configuration.ChangeAdd {
		t.Fatalf("changes = %#v, want selected add", got.Changes)
	}
}

func TestPrepareUsesSamePreservationContractAsPlan(t *testing.T) {
	inspection := inspectOwnedMap(
		t,
		`{"permission":{"bash":{"*":"allow"}}}`,
		`{"version":1,"actions":{"bash":{"*":"allow"}}}`,
		`{"bash":{"*":"allow"}}`,
	)
	prepared, err := inspection.PrepareWithPreservation(
		nil,
		[]domain.ComponentID{"credential-tools"},
	)
	if err != nil {
		t.Fatalf("PrepareWithPreservation() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("transitions = %#v, want none", prepared.Transitions())
	}
}
