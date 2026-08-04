package configuration

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type retiredClaimDisposition struct {
	claim releasecontract.JSONClaim
	prune bool
}

func reconcileRetiredClaims(
	document jsondocument.Document,
	registry *claimRegistry,
	ownership *releasecontract.JSONClaimOwnership,
	selected bool,
) (jsondocument.Document, []string, error) {
	active := make(map[string]bool, len(ownership.Claims))
	retiredClaims := make([]retiredClaimDisposition, 0)
	for _, claim := range ownership.Claims {
		active[claim.ID] = true
	}
	for identifier, state := range registry.Claims {
		if selected && active[identifier] {
			continue
		}
		retired, err := claimFromState(identifier, state)
		if err != nil {
			return document, nil, err
		}
		if selected {
			replacement, found, err := replacementClaim(retired, ownership.Claims)
			if err != nil {
				return document, nil, err
			}
			if found {
				if _, exists := registry.Claims[replacement.ID]; exists {
					return document, nil, fmt.Errorf("ambiguous replacement for retired claim %q", identifier)
				}
				registry.Claims[replacement.ID] = migratedClaimState(
					document, retired, replacement, state,
				)
				delete(registry.Claims, identifier)
				continue
			}
		}
		var prune bool
		document, prune, err = deselectJSONClaim(document, retired, state)
		if err != nil {
			return document, nil, err
		}
		retiredClaims = append(retiredClaims, retiredClaimDisposition{
			claim: retired, prune: prune,
		})
		delete(registry.Claims, identifier)
	}
	retained, candidates := classifyCreatedPointers(
		registry.CreatedPointers, registry.Claims, retiredClaims,
	)
	registry.CreatedPointers = retained
	return document, candidates, nil
}

func classifyCreatedPointers(
	pointers []string,
	active map[string]claimState,
	retired []retiredClaimDisposition,
) ([]string, []string) {
	retained := make([]string, 0, len(pointers))
	candidates := make([]string, 0, len(pointers))
	for _, raw := range pointers {
		if createdPointerMatchesStates(raw, active) {
			retained = append(retained, raw)
			continue
		}
		prunable, protected := retiredPointerDisposition(raw, retired)
		if prunable && !protected {
			candidates = append(candidates, raw)
		}
	}
	return retained, candidates
}

func createdPointerMatchesStates(raw string, states map[string]claimState) bool {
	for _, state := range states {
		if createdPointerMatchesClaim(raw, state.Pointer) {
			return true
		}
	}
	return false
}

func retiredPointerDisposition(
	raw string,
	retired []retiredClaimDisposition,
) (bool, bool) {
	prunable := false
	protected := false
	for _, disposition := range retired {
		if !createdPointerMatchesClaim(raw, disposition.claim.Pointer) {
			continue
		}
		if disposition.prune {
			prunable = true
		} else {
			protected = true
		}
	}
	return prunable, protected
}

func createdPointerMatchesClaim(createdRaw, claimRaw string) bool {
	created, _ := jsondocument.ParsePointer(createdRaw)
	claim, err := jsondocument.ParsePointer(claimRaw)
	return err == nil && len(created.Tokens()) <= len(claim.Tokens()) &&
		equalPointerPrefix(created.Tokens(), claim.Tokens())
}

func replacementClaim(
	retired releasecontract.JSONClaim,
	claims []releasecontract.JSONClaim,
) (releasecontract.JSONClaim, bool, error) {
	var result releasecontract.JSONClaim
	found := false
	for _, candidate := range claims {
		if !sameClaimIdentity(retired, candidate) {
			continue
		}
		if found {
			return releasecontract.JSONClaim{}, false, fmt.Errorf(
				"ambiguous replacement for retired claim %q",
				retired.ID,
			)
		}
		result, found = candidate, true
	}
	return result, found, nil
}

func sameClaimIdentity(
	left releasecontract.JSONClaim,
	right releasecontract.JSONClaim,
) bool {
	if left.Kind != right.Kind || left.Pointer != right.Pointer {
		return false
	}
	if left.Kind == releasecontract.JSONClaimExactScalar {
		return true
	}
	return left.SelectorPointer == right.SelectorPointer &&
		jsonValuesEqual(left.SelectorValue, right.SelectorValue)
}

func migratedClaimState(
	document jsondocument.Document,
	retired releasecontract.JSONClaim,
	replacement releasecontract.JSONClaim,
	state claimState,
) claimState {
	if state.State == "relinquished" || claimStateDrifted(document, retired, state) {
		return relinquishedState(replacement)
	}
	state.Kind = string(replacement.Kind)
	state.Pointer = replacement.Pointer
	if replacement.Kind == releasecontract.JSONClaimArrayEntry {
		state.Selector = &claimSelector{
			Pointer: replacement.SelectorPointer,
			Value:   json.RawMessage(replacement.SelectorValue),
		}
	}
	return state
}

func claimStateDrifted(
	document jsondocument.Document,
	claim releasecontract.JSONClaim,
	state claimState,
) bool {
	if claim.Kind == releasecontract.JSONClaimExactScalar {
		actual, present, err := claimValue(document, claim.Pointer)
		return err != nil || !present || !sameJSON(actual, state.Owned)
	}
	entries, err := claimArray(document, claim.Pointer)
	if err != nil {
		return true
	}
	matches := matchingEntries(entries, claim)
	return len(matches) != 1 || !sameJSON(entries[matches[0]], state.Owned)
}

func missingClaimPointers(
	document jsondocument.Document,
	raw string,
) []string {
	encoded := strings.Split(strings.TrimPrefix(raw, "/"), "/")
	result := make([]string, 0, len(encoded))
	for index := range encoded {
		candidate := "/" + strings.Join(encoded[:index+1], "/")
		pointer, _ := jsondocument.ParsePointer(candidate)
		_, status := document.LookupOrdered(pointer)
		if status == jsondocument.Missing {
			result = append(result, candidate)
		}
	}
	return result
}

func mergeCreatedPointers(left, right []string) []string {
	values := make(map[string]bool, len(left)+len(right))
	for _, pointer := range left {
		values[pointer] = true
	}
	for _, pointer := range right {
		values[pointer] = true
	}
	result := make([]string, 0, len(values))
	for pointer := range values {
		result = append(result, pointer)
	}
	sort.Strings(result)
	return result
}

func pruneCreatedPointers(
	document jsondocument.Document,
	pointers []string,
) (jsondocument.Document, []string, error) {
	ordered := append([]string(nil), pointers...)
	sort.Slice(ordered, func(left, right int) bool {
		return pointerDepth(ordered[left]) > pointerDepth(ordered[right])
	})
	remaining := make([]string, 0, len(ordered))
	for _, raw := range ordered {
		pointer, _ := jsondocument.ParsePointer(raw)
		value, status := document.LookupOrdered(pointer)
		if status == jsondocument.Missing {
			continue
		}
		if status == jsondocument.Incompatible {
			return document, nil, fmt.Errorf("created pointer %q is incompatible", raw)
		}
		if value != `{}` && value != `[]` {
			remaining = append(remaining, raw)
			continue
		}
		var err error
		document, err = document.Delete(pointer)
		if err != nil {
			return document, nil, err
		}
	}
	sort.Strings(remaining)
	return document, remaining, nil
}

func validCreatedPointers(pointers []string) bool {
	for index, raw := range pointers {
		if index > 0 && raw <= pointers[index-1] {
			return false
		}
		if _, err := jsondocument.ParsePointer(raw); err != nil {
			return false
		}
	}
	return true
}

func createdPointersMatchClaims(
	pointers []string,
	claims map[string]claimState,
) bool {
	claimTokens := make([][]string, 0, len(claims))
	for _, state := range claims {
		pointer, err := jsondocument.ParsePointer(state.Pointer)
		if err != nil {
			return false
		}
		claimTokens = append(claimTokens, pointer.Tokens())
	}
	for _, raw := range pointers {
		pointer, _ := jsondocument.ParsePointer(raw)
		created := pointer.Tokens()
		matched := false
		for _, claim := range claimTokens {
			if len(created) <= len(claim) &&
				equalPointerPrefix(created, claim) {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

func equalPointerPrefix(prefix, value []string) bool {
	for index := range prefix {
		if prefix[index] != value[index] {
			return false
		}
	}
	return true
}

func pointerDepth(raw string) int {
	return strings.Count(raw, "/")
}

func jsonValuesEqual(left, right string) bool {
	leftDocument, leftErr := jsondocument.Parse([]byte(left))
	rightDocument, rightErr := jsondocument.Parse([]byte(right))
	return leftErr == nil && rightErr == nil &&
		leftDocument.Canonical() == rightDocument.Canonical()
}
