package releasecontract

import (
	"encoding/json"
	"fmt"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const (
	jsonMapOwnershipKind  = "json-map-entry-registry-v1"
	decisionRuleSchema    = "decision-rule-v1"
	registrySchemaVersion = 1
	decisionRuleEntries   = "/actions"
)

func loadJSONMapOwnership(
	releaseRoot, sourceBase, source string,
	component domain.ComponentID,
	resourceTarget domain.Location,
	strategy ResourceStrategy,
	pointers optionalStringList,
	ownership optionalJSONMapOwnership,
	payloadRows []payloadFile,
) (*JSONMapOwnership, error) {
	if !ownership.Present {
		return nil, nil
	}
	if strategy != StrategyJSONKeyMerge {
		return nil, fmt.Errorf("JSON map ownership requires JSON merge strategy")
	}
	if pointers.Present {
		return nil, fmt.Errorf("JSON map ownership conflicts with owned JSON pointers")
	}
	loaded, err := validateJSONMapOwnership(component, ownership.Value)
	if err != nil {
		return nil, err
	}
	if loaded.RegistryTarget.Root != resourceTarget.Root {
		return nil, fmt.Errorf("ownership registry must use its resource target root")
	}
	if locationsOverlap(loaded.RegistryTarget, resourceTarget) {
		return nil, fmt.Errorf("ownership registry overlaps its resource target")
	}
	desired, err := loadDesiredOwnershipMap(
		releaseRoot, sourceBase, source, loaded.MapPointer, payloadRows,
	)
	if err != nil {
		return nil, err
	}
	if err := validateDecisionRuleMap(desired); err != nil {
		return nil, err
	}
	loaded.DesiredMap = desired
	return loaded, nil
}

func validateJSONMapOwnership(
	component domain.ComponentID,
	record jsonMapOwnershipRecord,
) (*JSONMapOwnership, error) {
	if record.Kind != jsonMapOwnershipKind || record.EntrySchema != decisionRuleSchema {
		return nil, fmt.Errorf("unsupported JSON map ownership")
	}
	if err := validateOwnershipPointer(record.MapPointer, "map"); err != nil {
		return nil, err
	}
	if record.Registry.SchemaVersion != registrySchemaVersion {
		return nil, fmt.Errorf("unsupported ownership registry schema")
	}
	if err := validateOwnershipPointer(record.Registry.EntriesPointer, "entries"); err != nil {
		return nil, err
	}
	if record.Registry.EntriesPointer != decisionRuleEntries {
		return nil, fmt.Errorf("unsupported ownership registry entries pointer")
	}
	target, err := location(record.Registry.Target)
	if err != nil {
		return nil, fmt.Errorf("ownership registry: %w", err)
	}
	if err := validateComponentTarget(component, target, "ownership registry"); err != nil {
		return nil, err
	}
	return &JSONMapOwnership{
		MapPointer:            record.MapPointer,
		EntrySchema:           record.EntrySchema,
		RegistryTarget:        target,
		RegistrySchemaVersion: record.Registry.SchemaVersion,
		EntriesPointer:        record.Registry.EntriesPointer,
	}, nil
}

func validateOwnershipPointer(raw, name string) error {
	if raw == "" {
		return fmt.Errorf("ownership %s pointer must not select the document root", name)
	}
	if _, err := jsondocument.ParsePointer(raw); err != nil {
		return fmt.Errorf("invalid ownership %s pointer: %w", name, err)
	}
	return nil
}

func loadDesiredOwnershipMap(
	releaseRoot, sourceBase, source, rawPointer string,
	payloadRows []payloadFile,
) (string, error) {
	expected, exists := payloadRecord(payloadRows, source)
	if !exists {
		return "", fmt.Errorf("JSON source is absent from payload inventory")
	}
	payload, err := readVerifiedPayload(releaseRoot, path.Join(sourceBase, source), expected)
	if err != nil {
		return "", err
	}
	document, err := jsondocument.Parse(payload)
	if err != nil {
		return "", fmt.Errorf("invalid JSON source: %w", err)
	}
	pointer, err := jsondocument.ParsePointer(rawPointer)
	if err != nil {
		return "", err
	}
	desired, status := document.LookupOrdered(pointer)
	if status != jsondocument.Found {
		return "", fmt.Errorf("ownership map pointer %q does not resolve through objects", rawPointer)
	}
	if _, err := jsondocument.Parse([]byte(desired)); err != nil {
		return "", fmt.Errorf("ownership map pointer %q must select an object", rawPointer)
	}
	return desired, nil
}

func validateDecisionRuleMap(raw string) error {
	var entries map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &entries); err != nil {
		return fmt.Errorf("invalid decision rule map: %w", err)
	}
	if entries == nil {
		return fmt.Errorf("decision rule map must be an object")
	}
	for key, value := range entries {
		if key == "" || !validDecisionRule(value) {
			return fmt.Errorf("invalid decision rule for entry %q", key)
		}
	}
	return nil
}

func validDecisionRule(raw json.RawMessage) bool {
	var decision string
	if json.Unmarshal(raw, &decision) == nil {
		return validDecision(decision)
	}
	var patterns map[string]string
	if json.Unmarshal(raw, &patterns) != nil || len(patterns) == 0 {
		return false
	}
	for pattern, value := range patterns {
		if pattern == "" || !validDecision(value) {
			return false
		}
	}
	return true
}

func validDecision(value string) bool {
	return value == "allow" || value == "ask" || value == "deny"
}

type ownershipRegistryTarget struct {
	resourceID string
	target     domain.Location
	shareable  bool
}

func validateGlobalOwnershipRegistries(
	manifests []bundleManifest,
	installTargets []domain.Location,
	resourceTargets []resourceTarget,
) error {
	registries, err := ownershipRegistryTargets(manifests)
	if err != nil {
		return err
	}
	for index, registry := range registries {
		if err := rejectInstallOverlap(registry.target, installTargets); err != nil {
			return fmt.Errorf("resource %q ownership registry: %w", registry.resourceID, err)
		}
		if err := rejectResourceOverlap(
			registry.resourceID, registry.target, MCPProjectionDocumentJSON, resourceTargets,
		); err != nil {
			return fmt.Errorf("resource %q ownership registry: %w", registry.resourceID, err)
		}
		if err := rejectOwnershipRegistryOverlap(index, registries); err != nil {
			return fmt.Errorf("resource %q ownership registry: %w", registry.resourceID, err)
		}
	}
	return nil
}

func ownershipRegistryTargets(
	manifests []bundleManifest,
) ([]ownershipRegistryTarget, error) {
	var targets []ownershipRegistryTarget
	for _, manifest := range manifests {
		for _, resource := range manifest.Resources {
			if !resource.Ownership.Present {
				continue
			}
			target, err := location(resource.Ownership.Value.Registry.Target)
			if err != nil {
				return nil, err
			}
			targets = append(targets, ownershipRegistryTarget{
				resourceID: resource.ID,
				target:     target,
			})
		}
		for _, projection := range manifest.MCPProjections {
			target, err := location(projection.Registry.Target)
			if err != nil {
				return nil, err
			}
			targets = append(targets, ownershipRegistryTarget{
				resourceID: projection.ID,
				target:     target,
				shareable:  true,
			})
		}
	}
	return targets, nil
}

func rejectOwnershipRegistryOverlap(
	index int,
	registries []ownershipRegistryTarget,
) error {
	for otherIndex, other := range registries {
		current := registries[index]
		if otherIndex == index {
			continue
		}
		if current.shareable && other.shareable && current.target == other.target {
			continue
		}
		if locationsOverlap(current.target, other.target) {
			return fmt.Errorf("registry targets overlap")
		}
	}
	return nil
}
