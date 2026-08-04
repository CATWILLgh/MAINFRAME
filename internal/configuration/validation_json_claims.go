package configuration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func validateJSONClaimResource(resource releasecontract.Resource) error {
	ownership := resource.JSONClaimOwnership
	if len(resource.OwnedJSONFields) != 0 || resource.JSONMapOwnership != nil ||
		!resource.SupportsApply() || ownership.RegistrySchemaVersion != 1 ||
		!ownership.RegistryTarget.Valid() || ownership.RegistryTarget.Root != resource.Target.Root ||
		locationsOverlap(resource.Target, ownership.RegistryTarget) || len(ownership.Claims) == 0 {
		return fmt.Errorf("invalid JSON claim ownership")
	}
	for index, claim := range ownership.Claims {
		if claim.ID == "" || (index > 0 && claim.ID <= ownership.Claims[index-1].ID) {
			return fmt.Errorf("JSON claims must be sorted and unique")
		}
		if _, err := jsondocument.ParsePointer(claim.Pointer); err != nil {
			return err
		}
		if claim.Kind == releasecontract.JSONClaimArrayEntry {
			if _, err := jsondocument.ParsePointer(claim.SelectorPointer); err != nil {
				return err
			}
		} else if claim.Kind != releasecontract.JSONClaimExactScalar {
			return fmt.Errorf("invalid JSON claim kind")
		}
	}
	return nil
}
