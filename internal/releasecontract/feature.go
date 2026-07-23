package releasecontract

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func installUnitFeature(
	schemaVersion int,
	unit installUnit,
) (domain.FeatureID, error) {
	feature := domain.FeatureID(unit.Feature.Value)
	if !unit.Feature.Present {
		return feature, nil
	}
	if schemaVersion < bundleSchemaVersionV5 {
		return "", fmt.Errorf(
			"install unit %q feature requires bundle schema version 5",
			unit.ID,
		)
	}
	if !feature.Valid() {
		return "", fmt.Errorf(
			"install unit %q has invalid feature %q",
			unit.ID,
			feature,
		)
	}
	return feature, nil
}
