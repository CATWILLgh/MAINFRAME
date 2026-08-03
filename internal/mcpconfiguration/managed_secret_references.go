package mcpconfiguration

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type ManagedSecretReference struct {
	Reference      string
	ComponentID    domain.ComponentID
	ResourceID     string
	RegistryTarget domain.Location
}

func ScanManagedSecretReferences(host Host) ([]ManagedSecretReference, error) {
	if host == nil {
		return nil, fmt.Errorf("host must not be nil")
	}
	var result []ManagedSecretReference
	for _, contract := range releasecontract.ManagedMCPRegistryContracts() {
		references, err := scanManagedRegistry(host, contract)
		if err != nil {
			return nil, err
		}
		result = append(result, references...)
	}
	sort.Slice(result, func(left, right int) bool {
		if result[left].ComponentID != result[right].ComponentID {
			return result[left].ComponentID < result[right].ComponentID
		}
		if result[left].ResourceID != result[right].ResourceID {
			return result[left].ResourceID < result[right].ResourceID
		}
		return result[left].Reference < result[right].Reference
	})
	return result, nil
}

func scanManagedRegistry(
	host Host,
	contract releasecontract.ManagedMCPRegistryContract,
) ([]ManagedSecretReference, error) {
	entry, err := host.Inspect(contract.RegistryTarget, true)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf(
			"inspect %s MCP ownership registry: %w",
			contract.ComponentID,
			err,
		)
	}
	if entry.Kind != hostfs.EntryRegular {
		return nil, fmt.Errorf(
			"%s MCP ownership registry is not a regular file",
			contract.ComponentID,
		)
	}
	servers, err := decodeManagedRegistry(entry.Content)
	if err != nil {
		return nil, fmt.Errorf(
			"%s MCP ownership registry is invalid: %w",
			contract.ComponentID,
			err,
		)
	}
	return managedRegistryReferences(contract, servers)
}

func decodeManagedRegistry(raw []byte) (map[string]json.RawMessage, error) {
	document, err := jsondocument.Parse(raw)
	if err != nil {
		return nil, fmt.Errorf("invalid JSON")
	}
	var root map[string]json.RawMessage
	if err := json.Unmarshal([]byte(document.Canonical()), &root); err != nil ||
		len(root) != 2 ||
		string(root["version"]) != "1" ||
		root["servers"] == nil {
		return nil, fmt.Errorf("invalid schema")
	}
	var servers map[string]json.RawMessage
	if err := json.Unmarshal(root["servers"], &servers); err != nil ||
		servers == nil {
		return nil, fmt.Errorf("invalid servers")
	}
	return servers, nil
}

func managedRegistryReferences(
	contract releasecontract.ManagedMCPRegistryContract,
	servers map[string]json.RawMessage,
) ([]ManagedSecretReference, error) {
	var result []ManagedSecretReference
	for resourceID, raw := range servers {
		reference, present, err := managedEntrySecretReference(
			contract.ComponentID,
			raw,
		)
		if err != nil {
			return nil, fmt.Errorf("resource %q: %w", resourceID, err)
		}
		if present {
			result = append(result, ManagedSecretReference{
				Reference:      reference,
				ComponentID:    contract.ComponentID,
				ResourceID:     resourceID,
				RegistryTarget: contract.RegistryTarget,
			})
		}
	}
	return result, nil
}

func managedEntrySecretReference(
	component domain.ComponentID,
	raw json.RawMessage,
) (string, bool, error) {
	if string(raw) == "null" {
		return "", false, nil
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return "", false, fmt.Errorf("ownership entry is invalid")
	}
	formatRaw, hasFormat := object["format"]
	if component == domain.ComponentOpenCode &&
		hasFormat &&
		string(formatRaw) == `"`+openCodeSecretRegistryFormat+`"` {
		return openCodeManagedSecretReference(raw)
	}
	if component == domain.ComponentAntigravity2 &&
		hasFormat &&
		string(formatRaw) == `"`+antigravitySecretRegistryFormat+`"` {
		return antigravityManagedSecretReference(raw)
	}
	if containsSecretReference(raw) {
		return "", false, fmt.Errorf("secret-bearing ownership entry is unrecognized")
	}
	return "", false, nil
}

func containsSecretReference(raw json.RawMessage) bool {
	var root any
	if json.Unmarshal(raw, &root) != nil {
		return false
	}
	pending := []any{root}
	for len(pending) > 0 {
		index := len(pending) - 1
		current := pending[index]
		pending = pending[:index]
		switch value := current.(type) {
		case map[string]any:
			for key, nested := range value {
				if key == "secret_reference" {
					return true
				}
				pending = append(pending, nested)
			}
		case []any:
			pending = append(pending, value...)
		}
	}
	return false
}

func openCodeManagedSecretReference(
	raw json.RawMessage,
) (string, bool, error) {
	var object map[string]json.RawMessage
	var entry openCodeSecretRegistryEntry
	if err := json.Unmarshal(raw, &object); err != nil ||
		len(object) != 6 ||
		json.Unmarshal(raw, &entry) != nil ||
		validateOpenCodeSecretRegistryEntry(entry, false) != nil {
		return "", false, fmt.Errorf("OpenCode secret ownership metadata is invalid")
	}
	return entry.SecretReference, true, nil
}

func antigravityManagedSecretReference(
	raw json.RawMessage,
) (string, bool, error) {
	var object map[string]json.RawMessage
	var entry antigravitySecretRegistryEntry
	if err := json.Unmarshal(raw, &object); err != nil ||
		len(object) != 5 ||
		json.Unmarshal(raw, &entry) != nil ||
		validateAntigravitySecretRegistryEntry(entry, false) != nil {
		return "", false, fmt.Errorf(
			"Antigravity secret ownership metadata is invalid",
		)
	}
	return entry.SecretReference, true, nil
}
