package releasecontract

import (
	"fmt"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func validateResources(
	releaseRoot, bundleRoot, sourceBase string,
	component domain.ComponentID,
	records []resourceRecord,
	payloadRows []payloadFile,
) ([]Resource, error) {
	identifiers := make([]string, len(records))
	resources := make([]Resource, len(records))
	for index, record := range records {
		identifiers[index] = record.ID
		resource, err := validateResourceRecord(
			releaseRoot, bundleRoot, sourceBase, component, record, payloadRows,
		)
		if err != nil {
			return nil, err
		}
		resources[index] = resource
	}
	if !sortedUnique(identifiers) {
		return nil, fmt.Errorf("component %q resources must be sorted and unique", component)
	}
	return resources, nil
}

func validateResourceRecord(
	releaseRoot, bundleRoot, sourceBase string,
	component domain.ComponentID,
	record resourceRecord,
	payloadRows []payloadFile,
) (Resource, error) {
	strategy := ResourceStrategy(record.Strategy)
	if !itemPattern.MatchString(record.ID) || !strategy.valid() {
		return Resource{}, fmt.Errorf("component %q has invalid resource %q", component, record.ID)
	}
	source, target, legacySources, err := validateResourceLocations(
		bundleRoot, sourceBase, component, record, strategy,
	)
	if err != nil {
		return Resource{}, err
	}
	observation := SupportStatus(record.Observation)
	externalState, err := validateExternalState(
		component, strategy, target, observation, record.ExternalState,
	)
	if err != nil {
		return Resource{}, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	if !validObservationSupport(strategy, observation, externalState != nil) ||
		record.Apply != string(SupportUnimplemented) {
		return Resource{}, fmt.Errorf("resource %q overstates lifecycle support", record.ID)
	}
	desiredLine, err := loadDesiredLine(bundleRoot, record.Source, strategy, observation)
	if err != nil {
		return Resource{}, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	mapOwnership, ownedFields, err := validateResourceOwnership(
		releaseRoot, sourceBase, component, record, target, strategy, observation, payloadRows,
	)
	if err != nil {
		return Resource{}, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	return Resource{
		ID: record.ID, ComponentID: component, Strategy: strategy,
		SourcePath: source, Target: target, LegacySourceSuffixes: legacySources,
		Observation: observation, Apply: SupportUnimplemented, DesiredLine: desiredLine,
		OwnedJSONFields: ownedFields, JSONMapOwnership: mapOwnership,
		ExternalState: externalState,
	}, nil
}

func validateResourceOwnership(
	releaseRoot, sourceBase string,
	component domain.ComponentID,
	record resourceRecord,
	target domain.Location,
	strategy ResourceStrategy,
	observation SupportStatus,
	payloadRows []payloadFile,
) (*JSONMapOwnership, []JSONField, error) {
	mapOwnership, err := loadJSONMapOwnership(
		releaseRoot, sourceBase, record.Source, component, target, strategy,
		record.OwnedJSONPointers, record.Ownership, payloadRows,
	)
	if err != nil {
		return nil, nil, err
	}
	if mapOwnership != nil && observation != SupportSupported {
		return nil, nil, fmt.Errorf("JSON map ownership requires supported observation")
	}
	ownedFields, err := loadOwnedJSONFields(
		releaseRoot, sourceBase, record.Source, strategy, observation,
		record.OwnedJSONPointers, mapOwnership != nil, payloadRows,
	)
	if err != nil {
		return nil, nil, err
	}
	return mapOwnership, ownedFields, nil
}

func validateResourceLocations(
	bundleRoot, sourceBase string,
	component domain.ComponentID,
	record resourceRecord,
	strategy ResourceStrategy,
) (domain.ArtifactPath, domain.Location, []domain.ArtifactPath, error) {
	requiresSource := strategy == StrategyJSONKeyMerge || strategy == StrategySeedIfAbsent ||
		strategy == StrategyShellLine || strategy == StrategyShellLineIfPresent ||
		record.ExternalState.Present
	if requiresSource != (record.Source != "") {
		return "", domain.Location{}, nil, fmt.Errorf(
			"resource %q has inconsistent source",
			record.ID,
		)
	}
	var source domain.ArtifactPath
	if record.Source != "" {
		if err := validateSource(bundleRoot, record.Source, "file"); err != nil {
			return "", domain.Location{}, nil, fmt.Errorf("resource %q: %w", record.ID, err)
		}
		source = domain.ArtifactPath(path.Join(sourceBase, record.Source))
	}
	target, err := location(record.Target)
	if err != nil {
		return "", domain.Location{}, nil, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	if err := validateComponentTarget(component, target, "resource"); err != nil {
		return "", domain.Location{}, nil, err
	}
	legacySources, err := portablePaths(record.LegacySourceSuffixes, true)
	if err != nil {
		return "", domain.Location{}, nil, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	return source, target, legacySources, nil
}

func validObservationSupport(
	strategy ResourceStrategy,
	support SupportStatus,
	hasExternalState bool,
) bool {
	if support == SupportUnimplemented {
		return !hasExternalState
	}
	if support != SupportSupported {
		return false
	}
	switch strategy {
	case StrategyJSONKeyMerge,
		StrategySeedIfAbsent,
		StrategyEnsureDir,
		StrategyShellLine,
		StrategyShellLineIfPresent:
		return true
	case StrategyManualAction:
		return hasExternalState
	default:
		return false
	}
}

func validateExternalState(
	component domain.ComponentID,
	strategy ResourceStrategy,
	target domain.Location,
	observation SupportStatus,
	record optionalExternalState,
) (*ExternalStateDescriptor, error) {
	if !record.Present {
		return nil, nil
	}
	kind := ExternalStateKind(record.Value.Kind)
	if kind != ExternalStateCodexHookTrust ||
		component != domain.ComponentCodex ||
		strategy != StrategyManualAction ||
		observation != SupportSupported ||
		target.Root != domain.RootCodexConfig ||
		target.Path != "hooks.json" {
		return nil, fmt.Errorf("invalid external state boundary")
	}
	return &ExternalStateDescriptor{Kind: kind}, nil
}
