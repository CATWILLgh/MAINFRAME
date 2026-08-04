package configuration_test

import (
	"encoding/json"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestJSONClaimCreatedScalarEmptyDriftSurvivesRelinquishAndDeselect(t *testing.T) {
	for _, drifted := range []string{`{}`, `[]`} {
		t.Run(drifted, func(t *testing.T) {
			resource := renamedScalarResource("scalar", `true`)
			selected := selectJSONClaimFixture(t, resource)
			var document map[string]any
			if err := json.Unmarshal(selected[resource.Target], &document); err != nil {
				t.Fatal(err)
			}
			var value any
			if err := json.Unmarshal([]byte(drifted), &value); err != nil {
				t.Fatal(err)
			}
			document["hooks"].(map[string]any)["enabled"] = value
			selected[resource.Target], _ = json.Marshal(document)

			inspection, err := configuration.Inspect(
				[]releasecontract.Resource{resource}, claimHost(selected),
			)
			if err != nil {
				t.Fatal(err)
			}
			prepared, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentZCodeDesktop},
			)
			if err != nil {
				t.Fatal(err)
			}
			relinquished := mutationContents(t, prepared)
			if _, changed := relinquished[resource.Target]; changed {
				t.Fatalf("relinquishment changed user value %s", drifted)
			}
			selected[resource.JSONClaimOwnership.RegistryTarget] =
				relinquished[resource.JSONClaimOwnership.RegistryTarget]

			inspection, err = configuration.Inspect(
				[]releasecontract.Resource{resource}, claimHost(selected),
			)
			if err != nil {
				t.Fatal(err)
			}
			prepared, err = inspection.Prepare(nil)
			if err != nil {
				t.Fatal(err)
			}
			deselected := mutationContents(t, prepared)
			if _, changed := deselected[resource.Target]; changed {
				t.Fatalf("deselect changed relinquished user value %s", drifted)
			}
			if removalTargets(prepared)[resource.Target] {
				t.Fatalf("deselect removed target containing user value %s", drifted)
			}
		})
	}
}

func TestJSONClaimCorruptCreatedLeafPreservesRestoredPredecessor(t *testing.T) {
	resource := renamedScalarResource("scalar", `true`)
	initial := claimHost(map[domain.Location][]byte{
		resource.Target: []byte(`{"hooks":{"enabled":{}}}`),
	})
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource}, initial,
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	)
	if err != nil {
		t.Fatal(err)
	}
	selected := mutationContents(t, prepared)
	var registry map[string]any
	registryTarget := resource.JSONClaimOwnership.RegistryTarget
	if err := json.Unmarshal(selected[registryTarget], &registry); err != nil {
		t.Fatal(err)
	}
	registry["created_pointers"] = []string{"/hooks/enabled"}
	selected[registryTarget], _ = json.Marshal(registry)

	inspection, err = configuration.Inspect(
		[]releasecontract.Resource{resource}, claimHost(selected),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err = inspection.Prepare(nil)
	if err != nil {
		t.Fatal(err)
	}
	after := mutationContents(t, prepared)[resource.Target]
	var restored map[string]any
	if err := json.Unmarshal(after, &restored); err != nil {
		t.Fatal(err)
	}
	hooks, ok := restored["hooks"].(map[string]any)
	if !ok {
		t.Fatalf("restored predecessor parent is absent: %s", after)
	}
	enabled, present := hooks["enabled"]
	object, objectPresent := enabled.(map[string]any)
	if !present || !objectPresent || len(object) != 0 {
		t.Fatalf("restored predecessor was not preserved: %s", after)
	}
}
