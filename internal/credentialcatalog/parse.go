package credentialcatalog

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const (
	schemaVersion       = 1
	definitionsKind     = "mainframe-credential-definitions"
	instancesKind       = "mainframe-credential-instances"
	maximumDocumentSize = 1 << 20
)

type definitionsDocument struct {
	SchemaVersion int                 `json:"schema_version"`
	Kind          string              `json:"kind"`
	Services      []ServiceDefinition `json:"services"`
}

type instancesDocument struct {
	SchemaVersion int        `json:"schema_version"`
	Kind          string     `json:"kind"`
	Instances     []Instance `json:"instances"`
}

func ParseDefinitions(
	payload []byte,
	mcp mcpcatalog.Catalog,
) (Definitions, error) {
	document, err := decodeDocument[definitionsDocument](payload, "definitions")
	if err != nil {
		return Definitions{}, err
	}
	if document.SchemaVersion != schemaVersion || document.Kind != definitionsKind {
		return Definitions{}, fmt.Errorf("unsupported credential definitions contract")
	}
	if err := validateDefinitions(document.Services, mcp); err != nil {
		return Definitions{}, err
	}
	return Definitions{services: cloneServices(document.Services)}, nil
}

func ParseInstances(
	payload []byte,
	definitions Definitions,
) (Instances, error) {
	document, err := decodeDocument[instancesDocument](payload, "instances")
	if err != nil {
		return Instances{}, err
	}
	if document.SchemaVersion != schemaVersion || document.Kind != instancesKind {
		return Instances{}, fmt.Errorf("unsupported credential instances contract")
	}
	if document.Instances == nil {
		return Instances{}, fmt.Errorf("credential instances must be an array")
	}
	if err := validateInstances(document.Instances, definitions); err != nil {
		return Instances{}, err
	}
	return Instances{instances: cloneInstances(document.Instances)}, nil
}

func decodeDocument[T any](payload []byte, label string) (T, error) {
	var result T
	if len(payload) > maximumDocumentSize {
		return result, fmt.Errorf("%s document exceeds size limit", label)
	}
	if _, err := jsondocument.Parse(payload); err != nil {
		return result, fmt.Errorf("validate %s JSON: %w", label, err)
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&result); err != nil {
		return result, fmt.Errorf("decode %s: %w", label, err)
	}
	var trailing json.RawMessage
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return result, fmt.Errorf("%s must contain one JSON document", label)
	}
	return result, nil
}
