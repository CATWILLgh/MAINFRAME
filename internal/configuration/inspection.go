package configuration

import (
	"errors"
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type Inspection struct {
	resources    []releasecontract.Resource
	observations []Observation
	ownedMaps    map[string]ownedMapSnapshot
	files        map[domain.Location]fileSnapshot
	managedFiles map[string]managedFileSnapshot
	jsonClaims   map[string]jsonClaimSnapshot
}

type ownedMapSnapshot struct {
	existingRaw     string
	ownedRaw        string
	existingOrder   map[string]string
	configPresent   bool
	registryPresent bool
}

type fileSnapshot struct {
	present          bool
	raw              []byte
	mode             uint32
	device           uint64
	inode            uint64
	birthSeconds     int64
	birthNanoseconds int64
	sha256           string
}

func Inspect(resources []releasecontract.Resource, host Host) (Inspection, error) {
	return InspectWithExternal(resources, host, nil)
}

func InspectWithExternal(
	resources []releasecontract.Resource,
	host Host,
	external ExternalObserver,
) (Inspection, error) {
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
		files:        make(map[domain.Location]fileSnapshot),
		managedFiles: make(map[string]managedFileSnapshot),
		jsonClaims:   make(map[string]jsonClaimSnapshot),
	}
	snapshots := make(map[domain.Location]jsonSnapshot)
	managedRegistries := make(map[domain.Location]fileSnapshot)
	for _, resource := range cloned {
		if resource.JSONClaimOwnership != nil {
			observation, state := observeJSONClaimResource(resource, host, snapshots)
			inspection.observations = append(inspection.observations, observation)
			if observation.Status != Attention {
				inspection.jsonClaims[resource.ID] = state
			}
			continue
		}
		if resource.FileOwnership != nil {
			observation, state := inspectManagedFile(
				resource,
				host,
				managedRegistries,
			)
			inspection.observations = append(
				inspection.observations,
				observation,
			)
			if observation.Status != Attention {
				inspection.managedFiles[resource.ID] = state
				inspection.files[resource.Target] = state.target
				inspection.files[resource.FileOwnership.RegistryTarget] = state.registry
			}
			continue
		}
		observation, err := observeResource(
			resource,
			host,
			snapshots,
			inspection.files,
			external,
		)
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
	for location, snapshot := range captureFileSnapshots(snapshots) {
		inspection.files[location] = snapshot
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
	_, existingRaw, configPresent, err := ownedConfigMap(
		config,
		resource.JSONMapOwnership.MapPointer,
	)
	if err != nil {
		return ownedMapSnapshot{}, err
	}
	_, ownedRaw, registryPresent, err := ownedRegistryMap(
		registry,
		resource.JSONMapOwnership,
	)
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
		configPresent: configPresent, registryPresent: registryPresent,
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
		if resource.SourceContent != nil {
			result[index].SourceContent = append(
				[]byte{},
				resource.SourceContent...,
			)
		}
		if resource.JSONMapOwnership != nil {
			ownership := *resource.JSONMapOwnership
			result[index].JSONMapOwnership = &ownership
		}
		if resource.JSONClaimOwnership != nil {
			ownership := *resource.JSONClaimOwnership
			ownership.Claims = append([]releasecontract.JSONClaim(nil), ownership.Claims...)
			result[index].JSONClaimOwnership = &ownership
		}
		if resource.FileOwnership != nil {
			ownership := *resource.FileOwnership
			result[index].FileOwnership = &ownership
		}
		if resource.ExternalState != nil {
			externalState := *resource.ExternalState
			result[index].ExternalState = &externalState
		}
	}
	return result
}

func captureFileSnapshots(
	snapshots map[domain.Location]jsonSnapshot,
) map[domain.Location]fileSnapshot {
	result := make(map[domain.Location]fileSnapshot, len(snapshots))
	for location, snapshot := range snapshots {
		if errors.Is(snapshot.err, fs.ErrNotExist) {
			result[location] = fileSnapshot{}
			continue
		}
		if snapshot.err != nil || snapshot.entry.Kind != hostfs.EntryRegular ||
			snapshot.parseErr != nil {
			continue
		}
		result[location] = fileSnapshot{
			present:          true,
			raw:              append([]byte(nil), snapshot.entry.Content...),
			mode:             snapshot.entry.Mode,
			device:           snapshot.entry.Device,
			inode:            snapshot.entry.Inode,
			birthSeconds:     snapshot.entry.BirthSeconds,
			birthNanoseconds: snapshot.entry.BirthNanoseconds,
		}
	}
	return result
}
