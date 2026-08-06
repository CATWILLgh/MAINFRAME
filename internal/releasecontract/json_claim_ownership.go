package releasecontract

import (
	"bytes"
	"encoding/json"
	"fmt"
	"path"
	"reflect"
	"sort"
	"strconv"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const jsonClaimOwnershipKind = "json-claim-registry-v1"

func loadJSONClaimOwnership(
	releaseRoot, sourceBase string,
	component domain.ComponentID,
	record resourceRecord,
	target domain.Location,
	strategy ResourceStrategy,
	observation SupportStatus,
	payloadRows []payloadFile,
) (*JSONClaimOwnership, error) {
	if !record.JSONClaimOwnership.Present {
		return nil, nil
	}
	if strategy != StrategyJSONKeyMerge || observation != SupportSupported {
		return nil, fmt.Errorf("JSON claim ownership requires supported JSON merge")
	}
	value := record.JSONClaimOwnership.Value
	if value.Kind != jsonClaimOwnershipKind || value.Registry.SchemaVersion != 1 {
		return nil, fmt.Errorf("unsupported JSON claim ownership")
	}
	registry, err := location(value.Registry.Target)
	if err != nil || registry.Root != target.Root || locationsOverlap(registry, target) {
		return nil, fmt.Errorf("invalid JSON claim ownership registry")
	}
	if err := validateComponentTarget(component, registry, "JSON claim ownership registry"); err != nil {
		return nil, err
	}
	expected, exists := payloadRecord(payloadRows, record.Source)
	if !exists {
		return nil, fmt.Errorf("JSON source is absent from payload inventory")
	}
	payload, err := readVerifiedPayload(
		releaseRoot, path.Join(sourceBase, record.Source), expected,
	)
	if err != nil {
		return nil, err
	}
	document, err := decodeClaimDocument(payload)
	if err != nil {
		return nil, err
	}
	claims, err := loadJSONClaims(value.Claims, document)
	if err != nil {
		return nil, err
	}
	return &JSONClaimOwnership{
		RegistryTarget: registry, RegistrySchemaVersion: 1, Claims: claims,
	}, nil
}

func decodeClaimDocument(payload []byte) (any, error) {
	if _, err := jsondocument.Parse(payload); err != nil {
		return nil, fmt.Errorf("invalid JSON claim source: %w", err)
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.UseNumber()
	var document any
	if err := decoder.Decode(&document); err != nil {
		return nil, err
	}
	return document, nil
}

func loadJSONClaims(records []jsonClaimRecord, document any) ([]JSONClaim, error) {
	if len(records) == 0 {
		return nil, fmt.Errorf("JSON claim ownership claims must not be empty")
	}
	if len(records) > MaxOwnedJSONPointers {
		return nil, fmt.Errorf("JSON claim ownership exceeds %d claims", MaxOwnedJSONPointers)
	}
	claims := make([]JSONClaim, len(records))
	for index, record := range records {
		if !itemPattern.MatchString(record.ID) ||
			(index > 0 && record.ID <= records[index-1].ID) {
			return nil, fmt.Errorf("JSON claim ownership claims must be sorted and unique")
		}
		claim, err := loadJSONClaim(record, document)
		if err != nil {
			return nil, fmt.Errorf("JSON claim %q: %w", record.ID, err)
		}
		claims[index] = claim
	}
	return claims, nil
}

func loadJSONClaim(record jsonClaimRecord, document any) (JSONClaim, error) {
	pointer, err := jsondocument.ParsePointer(record.Pointer)
	if err != nil {
		return JSONClaim{}, err
	}
	desired, exists := lookupJSONObjectValue(document, pointer.Tokens())
	if !exists {
		return JSONClaim{}, fmt.Errorf("pointer is unresolved")
	}
	claim := JSONClaim{ID: record.ID, Kind: JSONClaimKind(record.Kind), Pointer: record.Pointer}
	switch claim.Kind {
	case JSONClaimExactScalar:
		if record.Selector != nil || isJSONContainer(desired) {
			return JSONClaim{}, fmt.Errorf("exact scalar claim is invalid")
		}
	case JSONClaimArrayEntry:
		if record.Selector == nil {
			return JSONClaim{}, fmt.Errorf("array claim has no selector")
		}
		// A scalar array entry has nothing inside it to address, so the root
		// pointer selects the entry itself.
		var selectorTokens []string
		if record.Selector.Pointer != "" {
			selector, err := jsondocument.ParsePointer(record.Selector.Pointer)
			if err != nil {
				return JSONClaim{}, fmt.Errorf("invalid selector: %w", err)
			}
			selectorTokens = selector.Tokens()
		}
		selectorValue, err := canonicalRaw(record.Selector.Value)
		if err != nil {
			return JSONClaim{}, fmt.Errorf("invalid selector value: %w", err)
		}
		entries, valid := desired.([]any)
		if !valid {
			return JSONClaim{}, fmt.Errorf("array claim pointer does not select an array")
		}
		matches := make([]any, 0, 1)
		for _, entry := range entries {
			actual, found := lookupJSONValue(entry, selectorTokens)
			if found && canonicalValue(actual) == selectorValue {
				matches = append(matches, entry)
			}
		}
		if len(matches) != 1 {
			return JSONClaim{}, fmt.Errorf("selector must match exactly one source entry")
		}
		desired = matches[0]
		claim.SelectorPointer = record.Selector.Pointer
		claim.SelectorValue = selectorValue
	default:
		return JSONClaim{}, fmt.Errorf("unsupported kind")
	}
	claim.Desired = canonicalValue(desired)
	return claim, nil
}

func lookupJSONObjectValue(value any, tokens []string) (any, bool) {
	current := value
	for _, token := range tokens {
		object, valid := current.(map[string]any)
		if !valid {
			return nil, false
		}
		var exists bool
		current, exists = object[token]
		if !exists {
			return nil, false
		}
	}
	return current, true
}

func lookupJSONValue(value any, tokens []string) (any, bool) {
	current := value
	for _, token := range tokens {
		switch typed := current.(type) {
		case map[string]any:
			var exists bool
			current, exists = typed[token]
			if !exists {
				return nil, false
			}
		case []any:
			index, err := strconv.Atoi(token)
			if err != nil || index < 0 || index >= len(typed) {
				return nil, false
			}
			current = typed[index]
		default:
			return nil, false
		}
	}
	return current, true
}

func canonicalRaw(raw json.RawMessage) (string, error) {
	value, err := decodeClaimDocument(raw)
	if err != nil {
		return "", err
	}
	return canonicalValue(value), nil
}

func canonicalValue(value any) string {
	payload, _ := json.Marshal(value)
	return string(payload)
}

func isJSONContainer(value any) bool {
	switch value.(type) {
	case map[string]any, []any:
		return true
	default:
		return false
	}
}

func cloneJSONClaims(source []JSONClaim) []JSONClaim {
	return append([]JSONClaim(nil), source...)
}

func sortedClaimIDs(claims []JSONClaim) []string {
	result := make([]string, len(claims))
	for index, claim := range claims {
		result[index] = claim.ID
	}
	sort.Strings(result)
	return result
}

func jsonValuesEqual(left, right string) bool {
	var leftValue, rightValue any
	return json.Unmarshal([]byte(left), &leftValue) == nil &&
		json.Unmarshal([]byte(right), &rightValue) == nil &&
		reflect.DeepEqual(leftValue, rightValue)
}
