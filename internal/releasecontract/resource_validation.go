package releasecontract

import (
	"fmt"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func validateResources(
	releaseRoot, bundleRoot, sourceBase string,
	component domain.ComponentID,
	schemaVersion int,
	records []resourceRecord,
	payloadRows []payloadFile,
) ([]Resource, error) {
	identifiers := make([]string, len(records))
	resources := make([]Resource, len(records))
	for index, record := range records {
		identifiers[index] = record.ID
		resource, err := validateResourceRecord(
			releaseRoot, bundleRoot, sourceBase, component, record, payloadRows,
			schemaVersion,
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
	schemaVersion int,
) (Resource, error) {
	strategy := ResourceStrategy(record.Strategy)
	if !itemPattern.MatchString(record.ID) || !strategy.valid() {
		return Resource{}, fmt.Errorf("component %q has invalid resource %q", component, record.ID)
	}
	if err := validateResourceSchema(record, strategy, schemaVersion); err != nil {
		return Resource{}, err
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
	if !validObservationSupport(strategy, observation, externalState != nil) {
		return Resource{}, fmt.Errorf("resource %q overstates lifecycle support", record.ID)
	}
	desired, err := loadResourceDesiredState(
		releaseRoot, bundleRoot, sourceBase, component,
		record, target, strategy, observation, payloadRows,
	)
	if err != nil {
		return Resource{}, fmt.Errorf("resource %q: %w", record.ID, err)
	}
	resource := desired.resource(record, component, source, target, legacySources, externalState)
	if !validApplyDeclaration(resource) {
		return Resource{}, fmt.Errorf("resource %q overstates lifecycle support", record.ID)
	}
	return resource, nil
}

func validateResourceSchema(
	record resourceRecord,
	strategy ResourceStrategy,
	schemaVersion int,
) error {
	if strategy == StrategyExactJSONDocument &&
		schemaVersion < bundleSchemaVersionV4 {
		return fmt.Errorf(
			"resource %q requires bundle schema version 4 or newer",
			record.ID,
		)
	}
	if strategy == StrategyExactJSONDocument &&
		record.LegacySourceSuffixes.Present {
		return fmt.Errorf(
			"resource %q exact JSON document has foreign claim metadata",
			record.ID,
		)
	}
	if record.FileOwnership.Present && schemaVersion < bundleSchemaVersionV6 {
		return fmt.Errorf(
			"resource %q file ownership requires bundle schema version 6",
			record.ID,
		)
	}
	return nil
}

type resourceDesiredState struct {
	line          string
	content       []byte
	mapOwnership  *JSONMapOwnership
	ownedFields   []JSONField
	fileOwnership *FileOwnership
	exemplar      string
}

func loadResourceDesiredState(
	releaseRoot, bundleRoot, sourceBase string,
	component domain.ComponentID,
	record resourceRecord,
	target domain.Location,
	strategy ResourceStrategy,
	observation SupportStatus,
	payloadRows []payloadFile,
) (resourceDesiredState, error) {
	desiredLine, err := loadDesiredLine(bundleRoot, record.Source, strategy, observation)
	if err != nil {
		return resourceDesiredState{}, err
	}
	sourceContent, err := loadSeedContent(
		releaseRoot,
		sourceBase,
		record.Source,
		strategy,
		observation,
		payloadRows,
	)
	if err != nil {
		return resourceDesiredState{}, err
	}
	mapOwnership, ownedFields, err := validateResourceOwnership(
		releaseRoot, sourceBase, component, record, target, strategy, observation, payloadRows,
	)
	if err != nil {
		return resourceDesiredState{}, err
	}
	fileOwnership, err := validateFileOwnership(
		record, component, target, strategy, observation,
	)
	if err != nil {
		return resourceDesiredState{}, err
	}
	exemplar, err := loadExactJSONExemplar(
		releaseRoot,
		sourceBase,
		record.Source,
		strategy,
		observation,
		payloadRows,
	)
	if err != nil {
		return resourceDesiredState{}, err
	}
	return resourceDesiredState{
		line: desiredLine, content: sourceContent,
		mapOwnership: mapOwnership, ownedFields: ownedFields,
		fileOwnership: fileOwnership, exemplar: exemplar,
	}, nil
}

func (desired resourceDesiredState) resource(
	record resourceRecord,
	component domain.ComponentID,
	source domain.ArtifactPath,
	target domain.Location,
	legacySources []domain.ArtifactPath,
	externalState *ExternalStateDescriptor,
) Resource {
	return Resource{
		ID: record.ID, ComponentID: component,
		Strategy:   ResourceStrategy(record.Strategy),
		SourcePath: source, Target: target, LegacySourceSuffixes: legacySources,
		Observation:   SupportStatus(record.Observation),
		Apply:         SupportStatus(record.Apply),
		SourceContent: desired.content, DesiredLine: desired.line,
		OwnedJSONFields: desired.ownedFields, JSONMapOwnership: desired.mapOwnership,
		FileOwnership:     desired.fileOwnership,
		ExternalState:     externalState,
		ExactJSONExemplar: desired.exemplar,
	}
}

func validateFileOwnership(
	record resourceRecord,
	component domain.ComponentID,
	target domain.Location,
	strategy ResourceStrategy,
	observation SupportStatus,
) (*FileOwnership, error) {
	if !record.FileOwnership.Present {
		return nil, nil
	}
	value := record.FileOwnership.Value
	registry, err := location(value.Registry.Target)
	if err != nil {
		return nil, fmt.Errorf("invalid file ownership registry target: %w", err)
	}
	if value.Kind != "managed-file-registry-v1" ||
		value.Registry.SchemaVersion != 1 ||
		strategy != StrategySeedIfAbsent ||
		observation != SupportSupported ||
		registry.Root != target.Root ||
		locationsOverlap(target, registry) {
		return nil, fmt.Errorf("invalid file ownership")
	}
	if err := validateComponentTarget(component, registry, "file ownership registry"); err != nil {
		return nil, err
	}
	return &FileOwnership{
		RegistryTarget: registry, RegistrySchemaVersion: 1,
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
		strategy == StrategyExactJSONDocument ||
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
	legacySources, err := portablePaths(record.LegacySourceSuffixes.Values, true)
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
		StrategyShellLineIfPresent,
		StrategyExactJSONDocument:
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
