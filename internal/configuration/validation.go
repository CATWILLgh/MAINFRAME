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
		releasecontract.StrategyEnsureDir,
		releasecontract.StrategyShellLine,
		releasecontract.StrategyShellLineIfPresent:
		return true
	default:
		return false
	}
}

func validateResource(resource releasecontract.Resource) error {
	if resource.Apply != releasecontract.SupportUnimplemented {
		return fmt.Errorf("apply support must remain unimplemented")
	}
	if resource.Observation == releasecontract.SupportUnimplemented {
		if len(resource.OwnedJSONFields) != 0 {
			return fmt.Errorf("unimplemented observation has owned JSON fields")
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
		return validateJSONFields(resource.OwnedJSONFields)
	}
	if len(resource.OwnedJSONFields) != 0 {
		return fmt.Errorf("owned JSON fields require JSON merge strategy")
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
		}
		for _, field := range resource.OwnedJSONFields {
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
			ResourceExists: true, DirectoryExists: true, LinePresent: true, JSONFieldsMatch: true,
		},
		NeedsChange: {
			ResourceMissing: true, DirectoryMissing: true, LineMissing: true, JSONFieldsDrifted: true,
		},
		NotApplicable: {OptionalTargetMissing: true},
		Attention: {
			SymbolicLink: true, WrongKind: true, InspectionFailed: true, JSONDocumentInvalid: true,
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
	default:
		return false
	}
}
