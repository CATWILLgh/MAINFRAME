package releasecontract

import (
	"fmt"
	"io/fs"
	"os"
	"path"
	"reflect"
	"regexp"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

var componentPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`)
var itemPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$`)
var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var componentRoots = map[domain.ComponentID]map[domain.RootID]struct{}{
	"antigravity-2": {"antigravity-config": {}, "antigravity-data": {}},
	"claude-code":   {domain.RootClaudeConfig: {}},
	"codex":         {domain.RootCodexConfig: {}},
	"credential-tools": {
		domain.RootCredentialsConfig: {}, domain.RootHome: {}, domain.RootUserBin: {},
	},
	"mainframe-cli": {domain.RootUserBin: {}},
	"opencode":      {domain.RootOpenCodeConfig: {}},
}
var credentialToolsHomePaths = map[domain.ArtifactPath]struct{}{
	".bashrc": {}, ".profile": {}, ".zshenv": {},
}
var componentDependencies = map[domain.ComponentID]map[domain.ComponentID]struct{}{
	"antigravity-2":    {"credential-tools": {}, "mainframe-cli": {}},
	"claude-code":      {"credential-tools": {}, "mainframe-cli": {}},
	"codex":            {"credential-tools": {}, "mainframe-cli": {}},
	"credential-tools": {},
	"mainframe-cli":    {},
	"opencode":         {"credential-tools": {}, "mainframe-cli": {}},
}

// ValidReleaseIdentity checks the path-safe release ID and exact index digest.
func ValidReleaseIdentity(releaseID, indexSHA256 string) bool {
	return componentPattern.MatchString(releaseID) &&
		digestPattern.MatchString(indexSHA256)
}

func validateIndex(index releaseIndex) error {
	if index.SchemaVersion != releaseSchemaVersion || index.Kind != releaseKind {
		return fmt.Errorf("unsupported release contract")
	}
	if !componentPattern.MatchString(index.ReleaseID) || len(index.Manifests) == 0 {
		return fmt.Errorf("invalid release identity")
	}
	if index.MCPCatalog.Path != mcpCatalogPath {
		return fmt.Errorf("MCP catalog must use reserved release path %q", mcpCatalogPath)
	}
	if !domain.ArtifactPath(index.MCPCatalog.Path).Portable() ||
		!digestPattern.MatchString(index.MCPCatalog.SHA256) {
		return fmt.Errorf("invalid MCP catalog entry")
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
	releaseRoot, bundleRoot, sourceBase string,
	manifest bundleManifest,
) (installmodel.ComponentSpec, []Resource, error) {
	component := domain.ComponentID(manifest.Component)
	if !supportedBundleSchemaVersion(manifest.SchemaVersion) || manifest.Kind != bundleKind ||
		!componentPattern.MatchString(manifest.Component) || !manifestCollectionsPresent(manifest) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("invalid bundle identity")
	}
	if _, exists := componentRoots[component]; !exists {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("unknown release component %q", component)
	}
	if !sortedUnique(manifest.Dependencies) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("invalid dependencies for %q", component)
	}
	if err := validateHostRequirements(component, manifest); err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	actual, err := payloadInventory(bundleRoot)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	if !reflect.DeepEqual(manifest.PayloadFiles, actual) {
		return installmodel.ComponentSpec{}, nil, fmt.Errorf("bundle %q payload inventory mismatch", component)
	}
	artifacts, err := validateUnits(
		bundleRoot,
		sourceBase,
		component,
		manifest.SchemaVersion,
		manifest.InstallUnits,
	)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	legacy, err := validateLegacy(component, manifest.LegacyArtifacts)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	resources, err := validateResources(
		releaseRoot,
		bundleRoot,
		sourceBase,
		component,
		manifest.SchemaVersion,
		manifest.Resources,
		manifest.PayloadFiles,
	)
	if err != nil {
		return installmodel.ComponentSpec{}, nil, err
	}
	if err := validateExternalStateArtifacts(resources, artifacts); err != nil {
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

func validateExternalStateArtifacts(
	resources []Resource,
	artifacts []installmodel.ArtifactSpec,
) error {
	for _, resource := range resources {
		if resource.ExternalState == nil {
			continue
		}
		matched := false
		for _, artifact := range artifacts {
			if artifact.Target == resource.Target &&
				artifact.SourcePath == resource.SourcePath {
				matched = true
				break
			}
		}
		if !matched {
			return fmt.Errorf(
				"external state resource %q does not match an install unit",
				resource.ID,
			)
		}
	}
	return nil
}

func manifestCollectionsPresent(manifest bundleManifest) bool {
	common := manifest.Dependencies != nil &&
		manifest.InstallUnits != nil &&
		manifest.LegacyArtifacts != nil &&
		manifest.Resources != nil &&
		manifest.PayloadFiles != nil &&
		manifest.RuntimeProfile != nil && manifest.MCPProjections != nil
	if !common {
		return false
	}
	switch manifest.SchemaVersion {
	case bundleSchemaVersionV2:
		return !manifest.HostRequirements.Present
	case bundleSchemaVersionV3:
		return manifest.HostRequirements.Present
	case bundleSchemaVersionV4:
		return true
	case bundleSchemaVersionV5, bundleSchemaVersionV6:
		return true
	default:
		return false
	}
}

func supportedBundleSchemaVersion(version int) bool {
	return version >= bundleSchemaVersionV2 &&
		version <= bundleSchemaVersionV6
}

func validateHostRequirements(component domain.ComponentID, manifest bundleManifest) error {
	if manifest.SchemaVersion == bundleSchemaVersionV2 ||
		(manifest.SchemaVersion >= bundleSchemaVersionV4 &&
			!manifest.HostRequirements.Present) {
		return nil
	}
	rows := manifest.HostRequirements.Values
	if len(rows) == 0 {
		return fmt.Errorf("component %q host requirements must not be empty", component)
	}
	keys := make([]string, len(rows))
	for index, row := range rows {
		kind := HostRequirementKind(row.Kind)
		if kind != HostRequirementDarwinApplicationBundleV1 {
			return fmt.Errorf("component %q has unsupported host requirement kind %q", component, kind)
		}
		if strings.TrimSpace(row.BundleIdentifier) == "" || len(row.ExactVersions) == 0 {
			return fmt.Errorf("component %q has invalid host requirement", component)
		}
		for _, version := range row.ExactVersions {
			if strings.TrimSpace(version) == "" {
				return fmt.Errorf("component %q has an empty exact host version", component)
			}
		}
		if !sortedUnique(row.ExactVersions) {
			return fmt.Errorf("component %q host versions must be sorted and unique", component)
		}
		keys[index] = row.Kind + "\x00" + row.BundleIdentifier
	}
	if !sortedUnique(keys) {
		return fmt.Errorf("component %q host requirements must be sorted and unique", component)
	}
	return nil
}

func validateUnits(
	bundleRoot, sourceBase string,
	component domain.ComponentID,
	schemaVersion int,
	units []installUnit,
) ([]installmodel.ArtifactSpec, error) {
	identifiers := make([]string, len(units))
	artifacts := make([]installmodel.ArtifactSpec, len(units))
	for index, unit := range units {
		identifiers[index] = unit.ID
		if !domain.ValidUnitID(unit.ID) || (unit.Kind != "file" && unit.Kind != "tree") {
			return nil, fmt.Errorf("component %q has invalid install unit %q", component, unit.ID)
		}
		if err := validateSource(bundleRoot, unit.Source, unit.Kind); err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		target, err := location(unit.Target)
		if err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		if err := validateComponentTarget(component, target, "install unit"); err != nil {
			return nil, err
		}
		suffixes, err := portablePaths(unit.LegacySourceSuffixes, true)
		if err != nil {
			return nil, fmt.Errorf("install unit %q: %w", unit.ID, err)
		}
		feature, err := installUnitFeature(schemaVersion, unit)
		if err != nil {
			return nil, err
		}
		artifacts[index] = installmodel.ArtifactSpec{
			UnitID:               unit.ID,
			Target:               target,
			SourcePath:           domain.ArtifactPath(path.Join(sourceBase, unit.Source)),
			LegacyTargetSuffixes: suffixes,
			Feature:              feature,
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
		if err := validateComponentTarget(component, target, "legacy artifact"); err != nil {
			return nil, err
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
	if (kind == "file" && !info.Mode().IsRegular()) ||
		(kind == "tree" && !info.IsDir()) ||
		info.Mode()&fs.ModeSymlink != 0 {
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

func validateComponentTarget(
	component domain.ComponentID,
	target domain.Location,
	kind string,
) error {
	if _, exists := componentRoots[component][target.Root]; !exists {
		return fmt.Errorf(
			"component %q cannot target root %q from %s",
			component,
			target.Root,
			kind,
		)
	}
	if component == "credential-tools" && target.Root == domain.RootHome {
		if _, exists := credentialToolsHomePaths[target.Path]; !exists {
			return fmt.Errorf(
				"component %q cannot target path %q under root %q from %s",
				component,
				target.Path,
				target.Root,
				kind,
			)
		}
	}
	return nil
}

func validateComponentDependency(component, dependency domain.ComponentID) error {
	allowed, exists := componentDependencies[component]
	if !exists {
		return fmt.Errorf("unknown release component %q", component)
	}
	if _, exists := allowed[dependency]; !exists {
		return fmt.Errorf("component %q cannot depend on %q", component, dependency)
	}
	return nil
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
