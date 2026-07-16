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
		map[string]any{"bash": map[string]any{"": "deny"}},
		map[string]any{"bash": map[string]any{"*": true}},
	}
	for _, existing := range invalid {
		if _, _, err := reconcileOwnedMap(existing, map[string]any{}, map[string]any{}); err == nil {
			t.Fatalf("reconcileOwnedMap() accepted %#v", existing)
		}
	}
}
