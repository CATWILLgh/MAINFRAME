package configuration

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

func TestReconcileOwnedMapMatchesPermissionOwnershipContract(t *testing.T) {
	payload, err := os.ReadFile("testdata/opencode_permission_ownership.json")
	if err != nil {
		t.Fatalf("read ownership fixtures: %v", err)
	}
	var tests []struct {
		Name      string         `json:"name"`
		Existing  any            `json:"existing"`
		Generated map[string]any `json:"generated"`
		Owned     map[string]any `json:"owned"`
		Merged    any            `json:"merged"`
		NextOwned map[string]any `json:"next_owned"`
	}
	if err := json.Unmarshal(payload, &tests); err != nil {
		t.Fatalf("decode ownership fixtures: %v", err)
	}

	for _, test := range tests {
		t.Run(test.Name, func(t *testing.T) {
			got, gotOwned, err := reconcileOwnedMap(
				test.Existing,
				test.Generated,
				test.Owned,
			)
			if err != nil {
				t.Fatalf("reconcileOwnedMap() error = %v", err)
			}
			if !reflect.DeepEqual(got, test.Merged) {
				t.Fatalf("merged = %#v, want %#v", got, test.Merged)
			}
			if !reflect.DeepEqual(gotOwned, test.NextOwned) {
				t.Fatalf("ownership = %#v, want %#v", gotOwned, test.NextOwned)
			}
		})
	}
}

func TestReconcileOwnedMapRejectsInvalidDecisionRules(t *testing.T) {
	invalid := []any{
		"invalid",
		map[string]any{"bash": "invalid"},
		map[string]any{"bash": map[string]any{}},
		map[string]any{"bash": map[string]any{"": "deny"}},
		map[string]any{"bash": map[string]any{"*": true}},
	}
	for _, existing := range invalid {
		if _, _, err := reconcileOwnedMap(existing, map[string]any{}, map[string]any{}); err == nil {
			t.Fatalf("reconcileOwnedMap() accepted %#v", existing)
		}
	}
}

type orderedOwnershipCase struct {
	existing        string
	generated       string
	owned           string
	wantOwned       any
	wantMergedOrder string
	wantOwnedOrder  string
}

func TestReconcileOwnedJSONMapsPreservesNestedRuleOwnershipOrder(t *testing.T) {
	old := `{"bash":{"*":"allow","rm -rf /":"deny"}}`
	reversed := `{"bash":{"rm -rf /":"deny","*":"allow"}}`
	tests := map[string]orderedOwnershipCase{
		"equivalent unicode encoding stays managed": {
			existing:        `{"bash":{"а":"deny","*":"allow"}}`,
			generated:       `{"bash":{"а":"deny","*":"allow"}}`,
			owned:           `{"bash":{"\u0430":"deny","*":"allow"}}`,
			wantOwned:       map[string]any{"а": "deny", "*": "allow"},
			wantMergedOrder: `{"а":"deny","*":"allow"}`,
			wantOwnedOrder:  `{"а":"deny","*":"allow"}`,
		},
		"order-only user edit relinquishes ownership": {
			existing:        reversed,
			generated:       old,
			owned:           old,
			wantOwned:       nil,
			wantMergedOrder: `{"rm -rf /":"deny","*":"allow"}`,
		},
		"identical order stays managed": {
			existing:        old,
			generated:       old,
			owned:           old,
			wantOwned:       map[string]any{"*": "allow", "rm -rf /": "deny"},
			wantMergedOrder: `{"*":"allow","rm -rf /":"deny"}`,
			wantOwnedOrder:  `{"*":"allow","rm -rf /":"deny"}`,
		},
		"changed generated order updates managed rule": {
			existing:        old,
			generated:       reversed,
			owned:           old,
			wantOwned:       map[string]any{"rm -rf /": "deny", "*": "allow"},
			wantMergedOrder: `{"rm -rf /":"deny","*":"allow"}`,
			wantOwnedOrder:  `{"rm -rf /":"deny","*":"allow"}`,
		},
	}

	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			assertOrderedOwnership(t, test)
		})
	}
}

func assertOrderedOwnership(t *testing.T, test orderedOwnershipCase) {
	t.Helper()
	result, err := reconcileOwnedJSONMaps(
		test.existing,
		test.generated,
		test.owned,
	)
	if err != nil {
		t.Fatalf("reconcileOwnedJSONMaps() error = %v", err)
	}
	if !reflect.DeepEqual(result.nextOwned["bash"], test.wantOwned) {
		t.Fatalf(
			"ownership = %#v, want %#v",
			result.nextOwned["bash"],
			test.wantOwned,
		)
	}
	if result.mergedOrder["bash"] != test.wantMergedOrder {
		t.Fatalf(
			"merged order = %q, want %q",
			result.mergedOrder["bash"],
			test.wantMergedOrder,
		)
	}
	if result.nextOwnedOrder["bash"] != test.wantOwnedOrder {
		t.Fatalf(
			"ownership order = %q, want %q",
			result.nextOwnedOrder["bash"],
			test.wantOwnedOrder,
		)
	}
}
