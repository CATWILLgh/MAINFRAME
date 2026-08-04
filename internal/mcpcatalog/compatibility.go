package mcpcatalog

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func validateCompatibility(entries []AdapterCompatibility) error {
	ids := make([]string, len(entries))
	for index, entry := range entries {
		ids[index] = string(entry.Adapter)
		if !knownAdapter(entry.Adapter) {
			return fmt.Errorf("unknown adapter %q", entry.Adapter)
		}
		if (entry.Status == Supported && entry.Reason != "") ||
			(entry.Status == Unsupported && entry.Reason == "") {
			return fmt.Errorf("adapter %q has inconsistent support reason", entry.Adapter)
		}
		if entry.Status != Supported && entry.Status != Unsupported {
			return fmt.Errorf("adapter %q has invalid support status", entry.Adapter)
		}
	}
	if !sortedUnique(ids) {
		return fmt.Errorf("compatibility must be sorted with unique adapters")
	}
	if !completeCompatibilitySet(ids) {
		return fmt.Errorf("profile compatibility must classify every adapter")
	}
	return nil
}

func completeCompatibilitySet(ids []string) bool {
	if len(ids) == 5 {
		return true
	}
	legacy := []string{
		string(domain.ComponentAntigravity2),
		string(domain.ComponentClaudeCode),
		string(domain.ComponentCodex),
		string(domain.ComponentOpenCode),
	}
	if len(ids) != len(legacy) {
		return false
	}
	for index := range legacy {
		if ids[index] != legacy[index] {
			return false
		}
	}
	return true
}

func knownAdapter(id domain.ComponentID) bool {
	switch id {
	case domain.ComponentClaudeCode,
		domain.ComponentCodex,
		domain.ComponentOpenCode,
		domain.ComponentAntigravity2,
		domain.ComponentZCodeDesktop:
		return true
	default:
		return false
	}
}
