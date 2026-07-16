package configuration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type Inspection struct {
	resources    []releasecontract.Resource
	observations []Observation
	ownedMaps    map[string]ownedMapSnapshot
}

type ownedMapSnapshot struct {
	existingRaw   string
	ownedRaw      string
	existingOrder map[string]string
}

func Inspect(resources []releasecontract.Resource, host Host) (Inspection, error) {
	if host == nil {
		return Inspection{}, fmt.Errorf("host must not be nil")
	}
	cloned := cloneResources(resources)
	if err := validateResourceSet(cloned); err != nil {
		return Inspection{}, err
	}
	inspection := Inspection{
		resources:    cloned,
		observations: make([]Observation, 0, len(cloned)),
		ownedMaps:    make(map[string]ownedMapSnapshot),
	}
	snapshots := make(map[domain.Location]jsonSnapshot)
	for _, resource := range cloned {
		observation, err := observeResource(resource, host, snapshots)
		if err != nil {
			return Inspection{}, fmt.Errorf(
				"observe configuration resource %q: %w",
				resource.ID,
				err,
			)
		}
		inspection.observations = append(inspection.observations, observation)
		if resource.JSONMapOwnership != nil && observation.Status != Attention {
			state, err := captureOwnedMapSnapshot(resource, snapshots)
			if err != nil {
				return Inspection{}, fmt.Errorf(
					"capture configuration resource %q: %w",
					resource.ID,
					err,
				)
			}
			inspection.ownedMaps[resource.ID] = state
		}
	}
	if err := Validate(cloned, inspection.observations); err != nil {
		return Inspection{}, err
	}
	return inspection, nil
}

func (inspection Inspection) Observations() []Observation {
	return append([]Observation(nil), inspection.observations...)
}

func (inspection Inspection) Resources() []releasecontract.Resource {
	return cloneResources(inspection.resources)
}

func captureOwnedMapSnapshot(
	resource releasecontract.Resource,
	snapshots map[domain.Location]jsonSnapshot,
) (ownedMapSnapshot, error) {
	config := snapshots[resource.Target]
	registry := snapshots[resource.JSONMapOwnership.RegistryTarget]
	_, existingRaw, _, err := ownedConfigMap(
		config,
		resource.JSONMapOwnership.MapPointer,
	)
	if err != nil {
		return ownedMapSnapshot{}, err
	}
	_, ownedRaw, _, err := ownedRegistryMap(registry, resource.JSONMapOwnership)
	if err != nil {
		return ownedMapSnapshot{}, err
	}
	existingOrder, err := orderedRuleMap(existingRaw)
	if err != nil {
		return ownedMapSnapshot{}, err
	}
	return ownedMapSnapshot{
		existingRaw: existingRaw, ownedRaw: ownedRaw,
		existingOrder: existingOrder,
	}, nil
}

func cloneResources(resources []releasecontract.Resource) []releasecontract.Resource {
	result := make([]releasecontract.Resource, len(resources))
	for index, resource := range resources {
		result[index] = resource
		result[index].LegacySourceSuffixes = append(
			[]domain.ArtifactPath(nil),
			resource.LegacySourceSuffixes...,
		)
		result[index].OwnedJSONFields = append(
			[]releasecontract.JSONField(nil),
			resource.OwnedJSONFields...,
		)
		if resource.JSONMapOwnership != nil {
			ownership := *resource.JSONMapOwnership
			result[index].JSONMapOwnership = &ownership
		}
	}
	return result
}
