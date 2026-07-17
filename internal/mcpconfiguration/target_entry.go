package mcpconfiguration

import (
	"encoding/json"
	"math"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
	"github.com/pelletier/go-toml/v2"
)

func lookupTargetEntry(
	format releasecontract.MCPProjectionDocumentFormat,
	payload []byte,
	pointer jsondocument.Pointer,
) targetEntryObservation {
	switch format {
	case releasecontract.MCPProjectionDocumentJSON:
		document, err := jsondocument.Parse(payload)
		if err != nil {
			return targetEntryObservation{problem: "configuration JSON is invalid"}
		}
		raw, status := document.Lookup(pointer)
		return observationFromLookup(raw, status, true)
	case releasecontract.MCPProjectionDocumentTOML:
		return lookupTOMLEntry(payload, pointer)
	default:
		return targetEntryObservation{problem: "configuration document format is unsupported"}
	}
}

func lookupTOMLEntry(payload []byte, pointer jsondocument.Pointer) targetEntryObservation {
	root := make(map[string]any)
	if strings.TrimSpace(string(payload)) != "" {
		if err := toml.Unmarshal(payload, &root); err != nil {
			return targetEntryObservation{problem: "configuration TOML is invalid"}
		}
	}
	var current any = root
	for _, token := range pointer.Tokens() {
		object, valid := current.(map[string]any)
		if !valid {
			return targetEntryObservation{problem: "configuration MCP map is not a table"}
		}
		var exists bool
		current, exists = object[token]
		if !exists {
			return targetEntryObservation{comparable: true}
		}
	}
	if !hasJSONSemantics(current) {
		return targetEntryObservation{present: true}
	}
	canonical, err := json.Marshal(current)
	if err != nil {
		return targetEntryObservation{present: true}
	}
	return targetEntryObservation{
		present: true, comparable: true, raw: string(canonical),
	}
}

func observationFromLookup(
	raw string,
	status jsondocument.LookupStatus,
	comparable bool,
) targetEntryObservation {
	switch status {
	case jsondocument.Found:
		return targetEntryObservation{present: true, comparable: comparable, raw: raw}
	case jsondocument.Missing:
		return targetEntryObservation{comparable: true}
	default:
		return targetEntryObservation{problem: "configuration MCP map is not an object"}
	}
}

func hasJSONSemantics(value any) bool {
	switch typed := value.(type) {
	case nil, bool, string, int64:
		return true
	case float64:
		return !math.IsNaN(typed) && !math.IsInf(typed, 0)
	case []any:
		for _, item := range typed {
			if !hasJSONSemantics(item) {
				return false
			}
		}
		return true
	case map[string]any:
		for _, item := range typed {
			if !hasJSONSemantics(item) {
				return false
			}
		}
		return true
	default:
		return false
	}
}
