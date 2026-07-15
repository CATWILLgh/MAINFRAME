package releasecontract

import (
	"fmt"
	"io/fs"
	"os"
	"path"
	"reflect"
	"regexp"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

var componentPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var itemPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$`)
var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

func validateIndex(index releaseIndex) error {
	if index.SchemaVersion != schemaVersion || index.Kind != releaseKind {
		return fmt.Errorf("unsupported release contract")
	}
	if !componentPattern.MatchString(index.ReleaseID) || len(index.Manifests) == 0 {
		return fmt.Errorf("invalid release identity")
	}
	components := make([]string, len(index.Manifests))
	for position, entry := range index.Manifests {
		if !componentPattern.MatchString(entry.Component) ||
			!domain.ArtifactPath(entry.Path).Portable() ||
			!digestPattern.MatchString(entry.SHA256) {
			return fmt.Errorf("invalid manifest entry at position %d", position)
		}
		components[position] = entry.Component
	}
	if !sortedUnique(components) {
		return fmt.Errorf("release manifests must be sorted with unique components")
	}
	return nil
}

func validateBundle(
	bundleRoot, sourceBase string,
	manifest bundleManifest,
) (installmodel.ComponentSpec, []Resource, error) {
	component := domain.ComponentID(manifest.Component)
	if manifest.SchemaVersion != schemaVersion || manifest.Kind != bundleKind ||
		!componentPattern.MatchString(manifest.Component) || !manifestCollectionsPresent(manifest) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("invalid bundle identity")
	}
	if !sortedUnique(manifest.Dependencies) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("invalid dependencies for %q", component)
	}
	actual, err := payloadInventory(bundleRoot)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	if !reflect.DeepEqual(manifest.PayloadFiles, actual) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("bundle %q payload inventory mismatch", component)
	}
	artifacts, err := validateUnits(bundleRoot, sourceBase, component, manifest.InstallUnits)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	legacy, err := validateLegacy(component, manifest.LegacyArtifacts)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	resources, err := validateResources(bundleRoot, sourceBase, component, manifest.Resources)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	dependencies := make([]domain.ComponentID, len(manifest.Dependencies))
	for index, dependency := range manifest.Dependencies {
		dependencies[index] = domain.ComponentID(dependency)
	}
	return installmodel.ComponentSpec{
		ID: component, Dependencies: dependencies,
		Artifacts: artifacts, LegacyArtifacts: legacy,
	}, resources, nil
}

func manifestCollectionsPresent(manifest bundleManifest) bool {
	return manifest.Dependencies != nil &&
		manifest.InstallUnits != nil &&
		manifest.LegacyArtifacts != nil &&
		manifest.Resources != nil &&
		manifest.PayloadFiles != nil &&
		manifest.RuntimeProfile != nil
}

func validateUnits(
	bundleRoot, sourceBase string,
	component domain.ComponentID,
	units []installUnit,
) ([]installmodel.ArtifactSpec, error) {
	identifiers := make([]string, len(units))
	artifacts := make([]installmodel.ArtifactSpec, len(units))
	for index, unit := range units {
		identifiers[index] = unit.ID
		if !itemPattern.MatchString(unit.ID) || (unit.Kind != "file" && unit.Kind != "tree") {
			return nil, fmt.Errorf("component %q has invalid install unit %q", component, unit.ID)
		}
		if err := validateSource(bundleRoot, unit.Source, unit.Kind); err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		target, err := location(unit.Target)
		if err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		suffixes, err := portablePaths(unit.LegacySourceSuffixes, true)
		if err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		artifacts[index] = installmodel.ArtifactSpec{
			Target:               target,
			SourcePath:           domain.ArtifactPath(path.Join(sourceBase, unit.Source)),
			LegacyTargetSuffixes: suffixes,
		}
	}
	if !sortedUnique(identifiers) {
		return nil, fmt.Errorf("component %q install units must be sorted and unique", component)
	}
	return artifacts, nil
}

func validateLegacy(
	component domain.ComponentID,
	records []legacyArtifact,
) ([]installmodel.LegacyArtifactSpec, error) {
	artifacts := make([]installmodel.LegacyArtifactSpec, len(records))
	locations := make([]domain.Location, len(records))
	for index, record := range records {
		target, err := location(record.Target)
		if err != nil {
			return nil, fmt.Errorf("component %q legacy target: %w", component, err)
		}
		suffixes, err := portablePaths(record.TargetSuffixes, false)
		if err != nil {
			return nil, fmt.Errorf("component %q legacy target: %w", component, err)
		}
		locations[index] = target
		artifacts[index] = installmodel.LegacyArtifactSpec{Target: target, TargetSuffixes: suffixes}
	}
	if !sort.SliceIsSorted(locations, func(i, j int) bool {
		if locations[i].Root != locations[j].Root {
			return locations[i].Root < locations[j].Root
		}
		return locations[i].Path < locations[j].Path
	}) {
		return nil, fmt.Errorf("component %q legacy targets must be sorted", component)
	}
	return artifacts, nil
}

func validateResources(
	bundleRoot, sourceBase string,
	component domain.ComponentID,
	records []resourceRecord,
) ([]Resource, error) {
	identifiers := make([]string, len(records))
	resources := make([]Resource, len(records))
	for index, record := range records {
		identifiers[index] = record.ID
		strategy := ResourceStrategy(record.Strategy)
		if !itemPattern.MatchString(record.ID) || !strategy.valid() {
			return nil, fmt.Errorf("component %q has invalid resource %q", component, record.ID)
		}
		requiresSource := strategy == StrategyJSONKeyMerge ||
			strategy == StrategySeedIfAbsent ||
			strategy == StrategyShellLine ||
			strategy == StrategyShellLineIfPresent
		if requiresSource != (record.Source != "") {
			return nil, fmt.Errorf("resource %q has inconsistent source", record.ID)
		}
		var source domain.ArtifactPath
		if record.Source != "" {
			if err := validateSource(bundleRoot, record.Source, "file"); err != nil {
				return nil, fmt.Errorf("resource %q: %w", record.ID, err)
			}
			source = domain.ArtifactPath(path.Join(sourceBase, record.Source))
		}
		target, err := location(record.Target)
		if err != nil {
			return nil, fmt.Errorf("resource %q: %w", record.ID, err)
		}
		legacySources, err := portablePaths(record.LegacySourceSuffixes, true)
		if err != nil {
			return nil, fmt.Errorf("resource %q: %w", record.ID, err)
		}
		if record.Observation != string(SupportUnimplemented) || record.Apply != string(SupportUnimplemented) {
			return nil, fmt.Errorf("resource %q overstates lifecycle support", record.ID)
		}
		resources[index] = Resource{
			ID: record.ID, ComponentID: component, Strategy: strategy,
			SourcePath: source, Target: target, LegacySourceSuffixes: legacySources,
			Observation: SupportUnimplemented, Apply: SupportUnimplemented,
		}
	}
	if !sortedUnique(identifiers) {
		return nil, fmt.Errorf("component %q resources must be sorted and unique", component)
	}
	return resources, nil
}

func validateSource(bundleRoot, source, kind string) error {
	if !domain.ArtifactPath(source).Portable() {
		return fmt.Errorf("invalid source path %q", source)
	}
	resolved, err := safePath(bundleRoot, source)
	if err != nil {
		return err
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return err
	}
	if (kind == "file" && !info.Mode().IsRegular()) || (kind == "tree" && !info.IsDir()) || info.Mode()&fs.ModeSymlink != 0 {
		return fmt.Errorf("source %q does not match kind %q", source, kind)
	}
	return nil
}

func location(record locationRecord) (domain.Location, error) {
	value := domain.Location{Root: domain.RootID(record.Root), Path: domain.ArtifactPath(record.Path)}
	if !value.Root.Valid() || !value.Path.Portable() {
		return domain.Location{}, fmt.Errorf("invalid location %#v", record)
	}
	return value, nil
}

func portablePaths(values []string, allowEmpty bool) ([]domain.ArtifactPath, error) {
	if !allowEmpty && len(values) == 0 {
		return nil, fmt.Errorf("path list must not be empty")
	}
	if !sortedUnique(values) {
		return nil, fmt.Errorf("paths must be sorted and unique")
	}
	result := make([]domain.ArtifactPath, len(values))
	for index, value := range values {
		result[index] = domain.ArtifactPath(value)
		if !result[index].Portable() {
			return nil, fmt.Errorf("invalid path %q", value)
		}
	}
	return result, nil
}

func sortedUnique(values []string) bool {
	for index, value := range values {
		if index > 0 && value <= values[index-1] {
			return false
		}
	}
	return true
}
