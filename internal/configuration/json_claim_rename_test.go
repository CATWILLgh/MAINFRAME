package configuration_test

import (
	"encoding/json"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestRenamedScalarClaimPropagatesRelinquishmentAfterDrift(t *testing.T) {
	original := renamedScalarResource("scalar-old", `true`)
	selected := selectJSONClaimFixture(t, original)
	var document map[string]any
	if err := json.Unmarshal(selected[original.Target], &document); err != nil {
		t.Fatal(err)
	}
	document["hooks"].(map[string]any)["enabled"] = "user-edited"
	selected[original.Target], _ = json.Marshal(document)
	future := renamedScalarResource("scalar-new", `false`)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{future}, claimHost(selected),
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
	after := mutationContents(t, prepared)
	if _, changed := after[future.Target]; changed {
		t.Fatal("renamed scalar overwrote user drift")
	}
	registry := after[future.JSONClaimOwnership.RegistryTarget]
	if !bytesContains(registry, "scalar-new") ||
		!bytesContains(registry, "relinquished") ||
		bytesContains(registry, "scalar-old") {
		t.Fatalf("renamed relinquishment registry = %s", registry)
	}
}

func TestRenamedUnchangedScalarTransfersPredecessorAndUpdatesDesired(t *testing.T) {
	original := renamedScalarResource("scalar-old", `true`)
	selected := selectJSONClaimFixture(t, original)
	future := renamedScalarResource("scalar-new", `"renamed"`)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{future}, claimHost(selected),
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
	after := mutationContents(t, prepared)
	var document map[string]any
	if err := json.Unmarshal(after[future.Target], &document); err != nil {
		t.Fatal(err)
	}
	if document["hooks"].(map[string]any)["enabled"] != "renamed" {
		t.Fatalf("renamed desired value = %#v", document)
	}
	registry := after[future.JSONClaimOwnership.RegistryTarget]
	if !bytesContains(registry, "scalar-new") ||
		bytesContains(registry, "scalar-old") ||
		!bytesContains(registry, "predecessor_present") {
		t.Fatalf("transferred registry = %s", registry)
	}
}

func TestBootstrapDeselectPreservesForeignEmptyMembers(t *testing.T) {
	resource := jsonClaimResource()
	selected := selectJSONClaimFixture(t, resource)
	var document map[string]any
	if err := json.Unmarshal(selected[resource.Target], &document); err != nil {
		t.Fatal(err)
	}
	document["foreign-object"] = map[string]any{}
	document["foreign-array"] = []any{}
	selected[resource.Target], _ = json.Marshal(document)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource}, claimHost(selected),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(nil)
	if err != nil {
		t.Fatal(err)
	}
	if removalTargets(prepared)[resource.Target] {
		t.Fatal("foreign empty members caused target deletion")
	}
	after := mutationContents(t, prepared)[resource.Target]
	if !bytesContains(after, "foreign-object") ||
		!bytesContains(after, "foreign-array") {
		t.Fatalf("foreign empty members were removed: %s", after)
	}
}

func TestRenamedClaimFailsClosedOnAmbiguousRetiredIdentity(t *testing.T) {
	original := renamedScalarResource("scalar-old", `true`)
	selected := selectJSONClaimFixture(t, original)
	registryTarget := original.JSONClaimOwnership.RegistryTarget
	var registry map[string]any
	if err := json.Unmarshal(selected[registryTarget], &registry); err != nil {
		t.Fatal(err)
	}
	claims := registry["claims"].(map[string]any)
	claims["scalar-older"] = claims["scalar-old"]
	selected[registryTarget], _ = json.Marshal(registry)
	future := renamedScalarResource("scalar-new", `false`)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{future}, claimHost(selected),
	)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentZCodeDesktop},
	); err == nil {
		t.Fatal("ambiguous retired identity did not fail closed")
	}
}

func selectJSONClaimFixture(
	t *testing.T,
	resource releasecontract.Resource,
) map[domain.Location][]byte {
	t.Helper()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource}, claimHost(nil),
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
	return mutationContents(t, prepared)
}

func renamedScalarResource(
	identifier string,
	desired string,
) releasecontract.Resource {
	resource := jsonClaimResource()
	resource.JSONClaimOwnership.Claims = []releasecontract.JSONClaim{{
		ID: identifier, Kind: releasecontract.JSONClaimExactScalar,
		Pointer: "/hooks/enabled", Desired: desired,
	}}
	return resource
}
