package releasecontract

import (
	"fmt"
	"path"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

const MaxOwnedJSONPointers = 1024

func loadOwnedJSONFields(
	releaseRoot string,
	sourceBase string,
	source string,
	strategy ResourceStrategy,
	support SupportStatus,
	pointerValues optionalStringList,
	hasMapOwnership bool,
	payloadRows []payloadFile,
) ([]JSONField, error) {
	if strategy != StrategyJSONKeyMerge {
		if pointerValues.Present {
			return nil, fmt.Errorf("owned JSON pointers require JSON merge strategy")
		}
		return nil, nil
	}
	if support != SupportSupported {
		if pointerValues.Present {
			return nil, fmt.Errorf("owned JSON pointers require supported observation")
		}
		return nil, nil
	}
	if !pointerValues.Present {
		if hasMapOwnership {
			return nil, nil
		}
		return nil, fmt.Errorf("supported JSON observation requires owned JSON pointers")
	}
	pointers, err := validateOwnedPointers(pointerValues.Values)
	if err != nil {
		return nil, err
	}
	expected, exists := payloadRecord(payloadRows, source)
	if !exists {
		return nil, fmt.Errorf("JSON source is absent from payload inventory")
	}
	payload, err := readVerifiedPayload(releaseRoot, path.Join(sourceBase, source), expected)
	if err != nil {
		return nil, err
	}
	document, err := jsondocument.Parse(payload)
	if err != nil {
		return nil, fmt.Errorf("invalid JSON source: %w", err)
	}
	fields := make([]JSONField, len(pointers))
	for index, pointer := range pointers {
		desired, status := document.Lookup(pointer)
		if status != jsondocument.Found {
			return nil, fmt.Errorf("owned JSON pointer %q does not resolve through objects", pointerValues.Values[index])
		}
		fields[index] = JSONField{Pointer: pointerValues.Values[index], Desired: desired}
	}
	return fields, nil
}

func validateOwnedPointers(values []string) ([]jsondocument.Pointer, error) {
	if len(values) == 0 {
		return nil, fmt.Errorf("owned JSON pointers must be non-empty")
	}
	if len(values) > MaxOwnedJSONPointers {
		return nil, fmt.Errorf("owned JSON pointers must contain at most %d values", MaxOwnedJSONPointers)
	}
	if !sortedUnique(values) {
		return nil, fmt.Errorf("owned JSON pointers must be non-empty, sorted, and unique")
	}
	pointers := make([]jsondocument.Pointer, len(values))
	for index, value := range values {
		pointer, err := jsondocument.ParsePointer(value)
		if err != nil {
			return nil, err
		}
		for previous := 0; previous < index; previous++ {
			if jsondocument.Overlaps(pointers[previous], pointer) {
				return nil, fmt.Errorf("owned JSON pointers %q and %q overlap", values[previous], value)
			}
		}
		pointers[index] = pointer
	}
	return pointers, nil
}

func payloadRecord(rows []payloadFile, source string) (payloadFile, bool) {
	for _, row := range rows {
		if row.Path == source {
			return row, true
		}
	}
	return payloadFile{}, false
}

func validateGlobalJSONOwnership(manifests []bundleManifest) error {
	installTargets := make([]domain.Location, 0)
	resourceTargets := make([]resourceTarget, 0)
	for _, manifest := range manifests {
		for _, unit := range manifest.InstallUnits {
			target, err := location(unit.Target)
			if err != nil {
				return err
			}
			installTargets = append(installTargets, target)
		}
		for _, resource := range manifest.Resources {
			target, err := location(resource.Target)
			if err != nil {
				return err
			}
			resourceTargets = append(resourceTargets, resourceTarget{
				id: resource.ID, strategy: ResourceStrategy(resource.Strategy), target: target,
			})
		}
	}
	claims := make(map[domain.Location][]jsonClaim)
	for _, manifest := range manifests {
		for _, resource := range manifest.Resources {
			if resource.Strategy != string(StrategyJSONKeyMerge) {
				continue
			}
			target, err := location(resource.Target)
			if err != nil {
				return err
			}
			if err := rejectInstallOverlap(target, installTargets); err != nil {
				return fmt.Errorf("resource %q: %w", resource.ID, err)
			}
			if err := rejectResourceOverlap(resource.ID, target, resourceTargets); err != nil {
				return fmt.Errorf("resource %q: %w", resource.ID, err)
			}
			for _, raw := range resource.OwnedJSONPointers.Values {
				pointer, err := jsondocument.ParsePointer(raw)
				if err != nil {
					return err
				}
				if len(claims[target]) >= MaxOwnedJSONPointers {
					return fmt.Errorf("resource %q: too many owned JSON pointers for target", resource.ID)
				}
				if err := rejectClaimOverlap(raw, pointer, claims[target]); err != nil {
					return fmt.Errorf("resource %q: %w", resource.ID, err)
				}
				claims[target] = append(claims[target], jsonClaim{raw: raw, pointer: pointer})
			}
			if resource.Ownership.Present {
				raw := resource.Ownership.Value.MapPointer
				pointer, err := jsondocument.ParsePointer(raw)
				if err != nil {
					return err
				}
				if len(claims[target]) >= MaxOwnedJSONPointers {
					return fmt.Errorf("resource %q: too many owned JSON pointers for target", resource.ID)
				}
				if err := rejectClaimOverlap(raw, pointer, claims[target]); err != nil {
					return fmt.Errorf("resource %q: %w", resource.ID, err)
				}
				claims[target] = append(claims[target], jsonClaim{raw: raw, pointer: pointer})
			}
		}
	}
	return validateGlobalOwnershipRegistries(manifests, installTargets, resourceTargets)
}

type resourceTarget struct {
	id       string
	strategy ResourceStrategy
	target   domain.Location
}

type jsonClaim struct {
	raw     string
	pointer jsondocument.Pointer
}

func rejectInstallOverlap(target domain.Location, installTargets []domain.Location) error {
	for _, installTarget := range installTargets {
		if locationsOverlap(target, installTarget) {
			return fmt.Errorf("JSON target overlaps install target")
		}
	}
	return nil
}

func rejectClaimOverlap(
	raw string,
	pointer jsondocument.Pointer,
	claims []jsonClaim,
) error {
	for _, claim := range claims {
		if jsondocument.Overlaps(claim.pointer, pointer) {
			return fmt.Errorf("owned JSON pointers %q and %q overlap", claim.raw, raw)
		}
	}
	return nil
}

func rejectResourceOverlap(id string, target domain.Location, resources []resourceTarget) error {
	for _, other := range resources {
		if other.id == id || other.strategy == StrategyManualAction {
			continue
		}
		if other.strategy == StrategyJSONKeyMerge {
			if other.target != target && locationsOverlap(target, other.target) {
				return fmt.Errorf("JSON resource targets overlap")
			}
			continue
		}
		if !locationsOverlap(target, other.target) {
			continue
		}
		if other.strategy == StrategyEnsureDir && locationAncestor(other.target, target) {
			continue
		}
		return fmt.Errorf("JSON target overlaps non-JSON resource target")
	}
	return nil
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
