package releasecontract

import (
	"fmt"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

type diagnosticsDocument struct {
	SchemaVersion int   `json:"schema_version"`
	Events        *bool `json:"events"`
	Feedback      *bool `json:"feedback"`
}

func (resource Resource) ValidateExactJSONDocument(payload []byte) (string, error) {
	if resource.Strategy != StrategyExactJSONDocument ||
		resource.ExactJSONExemplar == "" {
		return "", fmt.Errorf("resource is not an exact JSON document")
	}
	return canonicalDiagnosticsDocument(payload)
}

func canonicalDiagnosticsDocument(payload []byte) (string, error) {
	document, err := jsondocument.Parse(payload)
	if err != nil {
		return "", fmt.Errorf("invalid diagnostics JSON: %w", err)
	}
	var decoded diagnosticsDocument
	if err := decodeStrict(payload, &decoded); err != nil {
		return "", fmt.Errorf("invalid diagnostics schema: %w", err)
	}
	if decoded.SchemaVersion != 1 ||
		decoded.Events == nil ||
		decoded.Feedback == nil {
		return "", fmt.Errorf("invalid diagnostics schema")
	}
	return document.Canonical(), nil
}

func loadExactJSONExemplar(
	releaseRoot string,
	sourceBase string,
	source string,
	strategy ResourceStrategy,
	support SupportStatus,
	payloadRows []payloadFile,
) (string, error) {
	if strategy != StrategyExactJSONDocument {
		return "", nil
	}
	if support != SupportSupported {
		return "", fmt.Errorf("exact JSON document requires supported observation")
	}
	expected, exists := payloadRecord(payloadRows, source)
	if !exists {
		return "", fmt.Errorf("exact JSON source is absent from payload inventory")
	}
	payload, err := readVerifiedPayload(
		releaseRoot,
		path.Join(sourceBase, source),
		expected,
	)
	if err != nil {
		return "", err
	}
	return canonicalDiagnosticsDocument(payload)
}
