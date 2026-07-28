package configuration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func (inspection Inspection) applyPreparedResources(
	builder *preparationBuilder,
	resources []releasecontract.Resource,
	selected map[domain.ComponentID]bool,
) error {
	for _, resource := range resources {
		if resource.FileOwnership != nil {
			if err := builder.applyManagedFile(
				resource,
				inspection.managedFiles[resource.ID],
				selected[resource.ComponentID],
			); err != nil {
				return fmt.Errorf(
					"prepare configuration resource %q: %w",
					resource.ID,
					err,
				)
			}
			continue
		}
		if resource.Strategy == releasecontract.StrategySeedIfAbsent {
			if err := builder.applySeed(resource, selected[resource.ComponentID]); err != nil {
				return fmt.Errorf(
					"prepare configuration resource %q: %w",
					resource.ID,
					err,
				)
			}
			continue
		}
		if err := builder.applyOwnedMap(
			resource,
			inspection.ownedMaps[resource.ID],
			selected[resource.ComponentID],
		); err != nil {
			return fmt.Errorf(
				"prepare configuration resource %q: %w",
				resource.ID,
				err,
			)
		}
	}
	return nil
}
