package configuration

import (
	"bytes"
	"encoding/json"
	"errors"
	"io/fs"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func observeOwnedJSONMap(
	resource releasecontract.Resource,
	host Host,
	snapshots map[domain.Location]jsonSnapshot,
) Observation {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	ownership := resource.JSONMapOwnership
	config := jsonSnapshotFor(resource.Target, host, snapshots)
	registry := jsonSnapshotFor(ownership.RegistryTarget, host, snapshots)
	if reason, unsafe := unsafeOwnedSnapshot(config); unsafe {
		result.Status, result.Reason = Attention, reason
		return result
	}
	if reason, unsafe := unsafeOwnedSnapshot(registry); unsafe {
		result.Status, result.Reason = Attention, reason
		return result
	}
	existing, existingRaw, configPresent, err := ownedConfigMap(
		config,
		ownership.MapPointer,
	)
	if err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	owned, ownedRaw, registryPresent, err := ownedRegistryMap(registry, ownership)
	if err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	generated, err := decodeDecisionMap(ownership.DesiredMap, false)
	if err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	merged, nextOwned, err := reconcileOwnedMap(existing, generated, owned)
	if err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	if configPresent && registryPresent &&
		reflect.DeepEqual(existing, merged) &&
		reflect.DeepEqual(owned, nextOwned) &&
		ownedRulesHaveDesiredOrder(
			existingRaw,
			ownedRaw,
			ownership.DesiredMap,
			nextOwned,
		) {
		result.Status, result.Reason = Ready, JSONFieldsMatch
		return result
	}
	result.Status, result.Reason = NeedsChange, JSONFieldsDrifted
	return result
}

func unsafeOwnedSnapshot(snapshot jsonSnapshot) (Reason, bool) {
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		return "", false
	}
	if snapshot.err != nil {
		return InspectionFailed, true
	}
	switch snapshot.entry.Kind {
	case hostfs.EntrySymlink:
		return SymbolicLink, true
	case hostfs.EntryRegular:
		if snapshot.parseErr != nil {
			return JSONDocumentInvalid, true
		}
		return "", false
	default:
		return WrongKind, true
	}
}

func ownedConfigMap(
	snapshot jsonSnapshot,
	rawPointer string,
) (any, string, bool, error) {
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		return map[string]any{}, `{}`, false, nil
	}
	pointer, err := jsondocument.ParsePointer(rawPointer)
	if err != nil {
		return nil, "", true, err
	}
	raw, status := snapshot.document.LookupOrdered(pointer)
	switch status {
	case jsondocument.Missing:
		return map[string]any{}, `{}`, true, nil
	case jsondocument.Found:
		value, err := decodeDecisionValue(raw)
		return value, raw, true, err
	default:
		return nil, "", true, errors.New("ownership map pointer is incompatible")
	}
}

func ownedRegistryMap(
	snapshot jsonSnapshot,
	ownership *releasecontract.JSONMapOwnership,
) (map[string]any, string, bool, error) {
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		return map[string]any{}, `{}`, false, nil
	}
	var root map[string]json.RawMessage
	if err := json.Unmarshal([]byte(snapshot.document.Canonical()), &root); err != nil {
		return nil, "", true, err
	}
	if len(root) != 2 || string(root["version"]) != "1" || root["actions"] == nil {
		return nil, "", true, errors.New("invalid ownership registry schema")
	}
	pointer, err := jsondocument.ParsePointer(ownership.EntriesPointer)
	if err != nil {
		return nil, "", true, err
	}
	raw, status := snapshot.document.LookupOrdered(pointer)
	if status != jsondocument.Found {
		return nil, "", true, errors.New("ownership entries pointer is unresolved")
	}
	owned, err := decodeDecisionMap(raw, true)
	return owned, raw, true, err
}

func ownedRulesHaveDesiredOrder(
	existingRaw, ownedRaw, desiredRaw string,
	nextOwned map[string]any,
) bool {
	existing, err := orderedRuleMap(existingRaw)
	if err != nil {
		return false
	}
	owned, err := orderedRuleMap(ownedRaw)
	if err != nil {
		return false
	}
	desired, err := orderedRuleMap(desiredRaw)
	if err != nil {
		return false
	}
	for action, value := range nextOwned {
		if value == nil {
			continue
		}
		want, generated := desired[action]
		if !generated || existing[action] != want || owned[action] != want {
			return false
		}
	}
	return true
}

func orderedRuleMap(raw string) (map[string]string, error) {
	if len(raw) == 0 || raw[0] != '{' {
		return map[string]string{}, nil
	}
	var entries map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &entries); err != nil {
		return nil, err
	}
	result := make(map[string]string, len(entries))
	for action, rule := range entries {
		var compact bytes.Buffer
		if err := json.Compact(&compact, rule); err != nil {
			return nil, err
		}
		result[action] = compact.String()
	}
	return result, nil
}
