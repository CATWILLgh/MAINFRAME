package configuration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func claimValue(document jsondocument.Document, raw string) (json.RawMessage, bool, error) {
	pointer, err := jsondocument.ParsePointer(raw)
	if err != nil {
		return nil, false, err
	}
	value, status := document.LookupOrdered(pointer)
	switch status {
	case jsondocument.Found:
		return json.RawMessage(value), true, nil
	case jsondocument.Missing:
		return nil, false, nil
	default:
		return nil, false, fmt.Errorf("claim pointer is incompatible")
	}
}

func claimArray(document jsondocument.Document, raw string) ([]json.RawMessage, error) {
	value, present, err := claimValue(document, raw)
	if err != nil || !present {
		return []json.RawMessage{}, err
	}
	var entries []json.RawMessage
	if err := json.Unmarshal(value, &entries); err != nil || entries == nil {
		return nil, fmt.Errorf("claim pointer does not select an array")
	}
	return entries, nil
}

func matchingEntries(entries []json.RawMessage, claim releasecontract.JSONClaim) []int {
	pointer, _ := jsondocument.ParsePointer(claim.SelectorPointer)
	var result []int
	for index, entry := range entries {
		var value any
		decoder := json.NewDecoder(bytes.NewReader(entry))
		decoder.UseNumber()
		if decoder.Decode(&value) != nil {
			continue
		}
		selected, found := lookupClaimSelector(value, pointer.Tokens())
		selectedRaw, _ := json.Marshal(selected)
		if found && sameJSON(selectedRaw, json.RawMessage(claim.SelectorValue)) {
			result = append(result, index)
		}
	}
	return result
}

func lookupClaimSelector(value any, tokens []string) (any, bool) {
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

func setClaimValue(
	document jsondocument.Document,
	raw string,
	value []byte,
) (jsondocument.Document, error) {
	pointer, err := jsondocument.ParsePointer(raw)
	if err != nil {
		return document, err
	}
	return document.Set(pointer, value)
}

func marshalRawArray(entries []json.RawMessage) []byte {
	payload, _ := json.Marshal(entries)
	return payload
}

func sameJSON(left, right json.RawMessage) bool {
	leftDocument, leftErr := jsondocument.Parse(left)
	rightDocument, rightErr := jsondocument.Parse(right)
	return leftErr == nil && rightErr == nil &&
		leftDocument.Canonical() == rightDocument.Canonical()
}

func cloneRaw(value json.RawMessage) json.RawMessage {
	return append(json.RawMessage(nil), value...)
}

func boolPointer(value bool) *bool { return &value }
