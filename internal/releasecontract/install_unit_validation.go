package releasecontract

import (
	"fmt"
	"io/fs"
	"os"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

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
		artifact, err := validateInstallUnit(bundleRoot, sourceBase, component, schemaVersion, unit)
		if err != nil {
			return nil, err
		}
		artifacts[index] = artifact
	}
	if !sortedUnique(identifiers) {
		return nil, fmt.Errorf("component %q install units must be sorted and unique", component)
	}
	return artifacts, nil
}

func validateInstallUnit(
	bundleRoot, sourceBase string,
	component domain.ComponentID,
	schemaVersion int,
	unit installUnit,
) (installmodel.ArtifactSpec, error) {
	if !domain.ValidUnitID(unit.ID) || (unit.Kind != "file" && unit.Kind != "tree") {
		return installmodel.ArtifactSpec{}, fmt.Errorf("component %q has invalid install unit %q", component, unit.ID)
	}
	materialization, err := installUnitMaterialization(schemaVersion, unit)
	if err != nil {
		return installmodel.ArtifactSpec{}, err
	}
	if err := validateSource(bundleRoot, unit.Source, unit.Kind); err != nil {
		return installmodel.ArtifactSpec{}, fmt.Errorf("install unit %q: %w", unit.ID, err)
	}
	target, err := location(unit.Target)
	if err != nil {
		return installmodel.ArtifactSpec{}, fmt.Errorf("install unit %q: %w", unit.ID, err)
	}
	if err := validateComponentTarget(component, target, "install unit"); err != nil {
		return installmodel.ArtifactSpec{}, err
	}
	suffixes, err := portablePaths(unit.LegacySourceSuffixes, true)
	if err != nil {
		return installmodel.ArtifactSpec{}, fmt.Errorf("install unit %q: %w", unit.ID, err)
	}
	feature, err := installUnitFeature(schemaVersion, unit)
	if err != nil {
		return installmodel.ArtifactSpec{}, err
	}
	sourceSHA256, err := installUnitSourceDigest(bundleRoot, unit, materialization)
	if err != nil {
		return installmodel.ArtifactSpec{}, err
	}
	return installmodel.ArtifactSpec{
		UnitID: unit.ID, Materialization: materialization, Target: target,
		SourcePath:   domain.ArtifactPath(path.Join(sourceBase, unit.Source)),
		SourceSHA256: sourceSHA256, LegacyTargetSuffixes: suffixes, Feature: feature,
	}, nil
}

func installUnitMaterialization(schemaVersion int, unit installUnit) (domain.Materialization, error) {
	if unit.Materialization.Present && schemaVersion < bundleSchemaVersionV8 {
		return "", fmt.Errorf("install unit %q materialization requires bundle schema version 8", unit.ID)
	}
	materialization := domain.Materialization(unit.Materialization.Value)
	if materialization == "" {
		materialization = domain.MaterializationSymlink
	}
	if !materialization.Valid() ||
		(materialization == domain.MaterializationWritableFile && unit.Kind != "file") {
		return "", fmt.Errorf("install unit %q has invalid materialization %q", unit.ID, unit.Materialization.Value)
	}
	return materialization, nil
}

func installUnitSourceDigest(
	bundleRoot string,
	unit installUnit,
	materialization domain.Materialization,
) (string, error) {
	if materialization != domain.MaterializationWritableFile {
		return "", nil
	}
	payload, err := readRegular(bundleRoot, unit.Source)
	if err != nil {
		return "", fmt.Errorf("install unit %q: %w", unit.ID, err)
	}
	return digestBytes(payload), nil
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
