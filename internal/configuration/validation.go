package configuration

import (
	"fmt"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func supportedStrategy(strategy releasecontract.ResourceStrategy) bool {
	switch strategy {
	case releasecontract.StrategySeedIfAbsent,
		releasecontract.StrategyJSONKeyMerge,
		releasecontract.StrategyExactJSONDocument,
		releasecontract.StrategyEnsureDir,
		releasecontract.StrategyShellLine,
		releasecontract.StrategyShellLineIfPresent:
		return true
	default:
		return false
	}
}

func validateResource(resource releasecontract.Resource) error {
	if resource.Apply != releasecontract.SupportUnimplemented &&
		!resource.SupportsApply() {
		return fmt.Errorf("invalid apply support")
	}
	if resource.Observation == releasecontract.SupportUnimplemented {
		if len(resource.OwnedJSONFields) != 0 || resource.JSONMapOwnership != nil ||
			resource.ExternalState != nil {
			return fmt.Errorf("unimplemented observation has lifecycle metadata")
		}
		return nil
	}
	if resource.Strategy == releasecontract.StrategyManualAction {
		if resource.Observation != releasecontract.SupportSupported ||
			resource.ExternalState == nil ||
			resource.ExternalState.Kind != releasecontract.ExternalStateCodexHookTrust ||
			resource.ComponentID != domain.ComponentCodex ||
			resource.Target.Root != domain.RootCodexConfig ||
			resource.Target.Path != "hooks.json" ||
			resource.SourcePath == "" {
			return fmt.Errorf("invalid external manual action")
		}
		if len(resource.OwnedJSONFields) != 0 || resource.JSONMapOwnership != nil {
			return fmt.Errorf("external manual action has JSON ownership")
		}
		return nil
	}
	if resource.Observation != releasecontract.SupportSupported || !supportedStrategy(resource.Strategy) {
		return fmt.Errorf("invalid observation support for strategy %q", resource.Strategy)
	}
	if (resource.Strategy == releasecontract.StrategyShellLine ||
		resource.Strategy == releasecontract.StrategyShellLineIfPresent) && resource.DesiredLine == "" {
		return fmt.Errorf("supported shell observation has no desired line")
	}
	if resource.Strategy == releasecontract.StrategyJSONKeyMerge {
		return validateJSONResource(resource)
	}
	if resource.Strategy == releasecontract.StrategyExactJSONDocument {
		if !resource.SupportsApply() {
			return fmt.Errorf("invalid exact JSON document capability")
		}
		return nil
	}
	if len(resource.OwnedJSONFields) != 0 || resource.JSONMapOwnership != nil {
		return fmt.Errorf("JSON ownership requires JSON merge strategy")
	}
	return nil
}

func validateJSONResource(resource releasecontract.Resource) error {
	ownership := resource.JSONMapOwnership
	if ownership == nil {
		return validateJSONFields(resource.OwnedJSONFields)
	}
	if len(resource.OwnedJSONFields) != 0 {
		return fmt.Errorf("JSON map ownership conflicts with owned JSON fields")
	}
	if ownership.EntrySchema != "decision-rule-v1" ||
		ownership.RegistrySchemaVersion != 1 ||
		ownership.EntriesPointer != "/actions" {
		return fmt.Errorf("unsupported JSON map ownership")
	}
	if _, err := jsondocument.ParsePointer(ownership.MapPointer); err != nil {
		return fmt.Errorf("invalid ownership map pointer: %w", err)
	}
	if !ownership.RegistryTarget.Valid() ||
		ownership.RegistryTarget.Root != resource.Target.Root ||
		locationsOverlap(resource.Target, ownership.RegistryTarget) {
		return fmt.Errorf("invalid ownership registry target")
	}
	document, err := jsondocument.Parse([]byte(ownership.DesiredMap))
	if err != nil || document.Compact() != ownership.DesiredMap {
		return fmt.Errorf("ownership desired map is not compact")
	}
	if _, err := decodeDecisionMap(ownership.DesiredMap, false); err != nil {
		return fmt.Errorf("invalid ownership desired map: %w", err)
	}
	return nil
}

func validateResourceSet(resources []releasecontract.Resource) error {
	seen := make(map[string]bool, len(resources))
	claims := make(map[domain.Location][]jsondocument.Pointer)
	validated := make([]releasecontract.Resource, 0, len(resources))
	for _, resource := range resources {
		if resource.ID == "" || seen[resource.ID] {
			return fmt.Errorf("invalid duplicate configuration resource %q", resource.ID)
		}
		if err := validateResource(resource); err != nil {
			return fmt.Errorf("invalid configuration resource %q: %w", resource.ID, err)
		}
		seen[resource.ID] = true
		for _, previous := range validated {
			if err := validateTargetCompatibility(resource, previous); err != nil {
				return fmt.Errorf("invalid configuration resource %q: %w", resource.ID, err)
			}
			if err := validateOwnershipCompatibility(resource, previous); err != nil {
				return fmt.Errorf("invalid configuration resource %q: %w", resource.ID, err)
			}
		}
		resourceClaims := append(
			[]releasecontract.JSONField(nil),
			resource.OwnedJSONFields...,
		)
		if resource.JSONMapOwnership != nil {
			resourceClaims = append(resourceClaims, releasecontract.JSONField{
				Pointer: resource.JSONMapOwnership.MapPointer,
			})
		}
		for _, field := range resourceClaims {
			pointer, _ := jsondocument.ParsePointer(field.Pointer)
			if len(claims[resource.Target]) >= releasecontract.MaxOwnedJSONPointers {
				return fmt.Errorf("too many owned JSON fields for configuration target")
			}
			for _, claim := range claims[resource.Target] {
				if jsondocument.Overlaps(claim, pointer) {
					return fmt.Errorf("configuration resources claim overlapping JSON fields")
				}
			}
			claims[resource.Target] = append(claims[resource.Target], pointer)
		}
		validated = append(validated, resource)
	}
	return nil
}

func validateOwnershipCompatibility(
	left releasecontract.Resource,
	right releasecontract.Resource,
) error {
	if left.JSONMapOwnership != nil {
		if err := validateRegistryAgainstResource(
			left.JSONMapOwnership.RegistryTarget,
			right,
		); err != nil {
			return err
		}
	}
	if right.JSONMapOwnership != nil {
		if err := validateRegistryAgainstResource(
			right.JSONMapOwnership.RegistryTarget,
			left,
		); err != nil {
			return err
		}
	}
	if left.JSONMapOwnership != nil && right.JSONMapOwnership != nil &&
		locationsOverlap(
			left.JSONMapOwnership.RegistryTarget,
			right.JSONMapOwnership.RegistryTarget,
		) {
		return fmt.Errorf("ownership registry targets overlap")
	}
	return nil
}

func validateRegistryAgainstResource(
	registry domain.Location,
	resource releasecontract.Resource,
) error {
	if resource.Strategy == releasecontract.StrategyManualAction ||
		!locationsOverlap(registry, resource.Target) {
		return nil
	}
	if resource.Strategy == releasecontract.StrategyEnsureDir &&
		locationAncestor(resource.Target, registry) {
		return nil
	}
	return fmt.Errorf("ownership registry overlaps configuration resource")
}

func validateTargetCompatibility(left, right releasecontract.Resource) error {
	if left.Strategy != releasecontract.StrategyJSONKeyMerge &&
		right.Strategy != releasecontract.StrategyJSONKeyMerge {
		return nil
	}
	jsonResource, other := left, right
	if right.Strategy == releasecontract.StrategyJSONKeyMerge {
		jsonResource, other = right, left
	}
	if other.Strategy == releasecontract.StrategyManualAction {
		return nil
	}
	if other.Strategy == releasecontract.StrategyJSONKeyMerge {
		if jsonResource.Target != other.Target && locationsOverlap(jsonResource.Target, other.Target) {
			return fmt.Errorf("JSON resource targets overlap")
		}
		return nil
	}
	if !locationsOverlap(jsonResource.Target, other.Target) {
		return nil
	}
	if other.Strategy == releasecontract.StrategyEnsureDir && locationAncestor(other.Target, jsonResource.Target) {
		return nil
	}
	return fmt.Errorf("JSON target overlaps non-JSON resource target")
}

func locationAncestor(parent, child domain.Location) bool {
	return parent.Root == child.Root &&
		strings.HasPrefix(string(child.Path), string(parent.Path)+"/")
}

func locationsOverlap(left, right domain.Location) bool {
	if left.Root != right.Root {
		return false
	}
	leftPath, rightPath := string(left.Path), string(right.Path)
	return leftPath == rightPath ||
		strings.HasPrefix(leftPath, rightPath+"/") ||
		strings.HasPrefix(rightPath, leftPath+"/")
}

func validateJSONFields(fields []releasecontract.JSONField) error {
	if len(fields) == 0 {
		return fmt.Errorf("supported JSON observation has no owned fields")
	}
	if len(fields) > releasecontract.MaxOwnedJSONPointers {
		return fmt.Errorf("supported JSON observation has at most %d owned fields", releasecontract.MaxOwnedJSONPointers)
	}
	pointers := make([]jsondocument.Pointer, len(fields))
	for index, field := range fields {
		if index > 0 && field.Pointer <= fields[index-1].Pointer {
			return fmt.Errorf("owned JSON fields must be sorted and unique")
		}
		pointer, err := jsondocument.ParsePointer(field.Pointer)
		if err != nil {
			return err
		}
		for previous := 0; previous < index; previous++ {
			if jsondocument.Overlaps(pointers[previous], pointer) {
				return fmt.Errorf("owned JSON fields overlap")
			}
		}
		desired, err := jsondocument.Parse([]byte(field.Desired))
		if err != nil || desired.Canonical() != field.Desired {
			return fmt.Errorf("owned JSON desired value is not canonical")
		}
		pointers[index] = pointer
	}
	return nil
}

func validObservation(resource releasecontract.Resource, observation Observation) bool {
	if resource.Observation == releasecontract.SupportUnimplemented {
		return observation.Status == NotAssessed && observation.Reason == ObservationUnsupported
	}
	valid := map[Status]map[Reason]bool{
		Ready: {
			ResourceExists: true, DirectoryExists: true, LinePresent: true,
			JSONFieldsMatch: true, ExternalStateSatisfied: true,
		},
		NeedsChange: {
			ResourceMissing: true, DirectoryMissing: true, LineMissing: true,
			JSONFieldsDrifted: true, ManualActionRequired: true,
		},
		NotApplicable: {OptionalTargetMissing: true},
		NotAssessed:   {ExternalStateUnavailable: true},
		Attention: {
			SymbolicLink: true, WrongKind: true, InspectionFailed: true,
			JSONDocumentInvalid: true, ExternalInspectionFailed: true,
		},
	}
	if !valid[observation.Status][observation.Reason] {
		return false
	}
	return reasonMatchesStrategy(resource.Strategy, observation.Reason)
}

func reasonMatchesStrategy(strategy releasecontract.ResourceStrategy, reason Reason) bool {
	switch strategy {
	case releasecontract.StrategyJSONKeyMerge:
		return reason == JSONFieldsMatch || reason == JSONFieldsDrifted ||
			reason == ResourceMissing || reason == SymbolicLink || reason == WrongKind ||
			reason == InspectionFailed || reason == JSONDocumentInvalid
	case releasecontract.StrategyExactJSONDocument:
		return reason == JSONFieldsMatch || reason == JSONFieldsDrifted ||
			reason == ResourceMissing || reason == SymbolicLink || reason == WrongKind ||
			reason == InspectionFailed || reason == JSONDocumentInvalid
	case releasecontract.StrategySeedIfAbsent:
		return reason == ResourceExists || reason == ResourceMissing || reason == SymbolicLink ||
			reason == WrongKind || reason == InspectionFailed
	case releasecontract.StrategyEnsureDir:
		return reason == DirectoryExists || reason == DirectoryMissing || reason == SymbolicLink ||
			reason == WrongKind || reason == InspectionFailed
	case releasecontract.StrategyShellLine:
		return reason == LinePresent || reason == LineMissing || reason == SymbolicLink ||
			reason == WrongKind || reason == InspectionFailed
	case releasecontract.StrategyShellLineIfPresent:
		return reason == LinePresent || reason == LineMissing || reason == OptionalTargetMissing ||
			reason == SymbolicLink || reason == WrongKind || reason == InspectionFailed
	case releasecontract.StrategyManualAction:
		return reason == ExternalStateSatisfied || reason == ManualActionRequired ||
			reason == ExternalStateUnavailable || reason == ExternalInspectionFailed
	default:
		return false
	}
}
