package releasecontract

import (
	"fmt"
	"path"
	"path/filepath"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const maxMCPCatalogBytes int64 = 1 << 20

func Load(root string) (Release, error) {
	canonical, err := canonicalRoot(root)
	if err != nil {
		return Release{}, err
	}
	indexPayload, err := readRegular(canonical, "release.json")
	if err != nil {
		return Release{}, fmt.Errorf("read release index: %w", err)
	}
	var index releaseIndex
	if err := decodeStrict(indexPayload, &index); err != nil {
		return Release{}, fmt.Errorf("decode release index: %w", err)
	}
	if err := validateIndex(index); err != nil {
		return Release{}, err
	}
	catalogPayload, err := readRegularBounded(canonical, index.MCPCatalog.Path, maxMCPCatalogBytes)
	if err != nil {
		return Release{}, fmt.Errorf("read MCP catalog: %w", err)
	}
	if digestBytes(catalogPayload) != index.MCPCatalog.SHA256 {
		return Release{}, fmt.Errorf("MCP catalog digest mismatch")
	}
	catalog, err := mcpcatalog.Parse(catalogPayload)
	if err != nil {
		return Release{}, fmt.Errorf("decode MCP catalog: %w", err)
	}
	components := make([]installmodel.ComponentSpec, 0, len(index.Manifests))
	resources := make([]Resource, 0)
	manifests := make([]bundleManifest, 0, len(index.Manifests))
	for _, entry := range index.Manifests {
		manifest, component, records, err := loadBundle(canonical, entry)
		if err != nil {
			return Release{}, err
		}
		manifests = append(manifests, manifest)
		components = append(components, component)
		resources = append(resources, records...)
	}
	if err := validateGlobal(manifests); err != nil {
		return Release{}, err
	}
	projections, err := loadMCPProjections(manifests, catalog)
	if err != nil {
		return Release{}, err
	}
	if err := validateClosedReleaseTree(canonical, index, manifests); err != nil {
		return Release{}, err
	}
	model, err := installmodel.New(components)
	if err != nil {
		return Release{}, fmt.Errorf("build release install model: %w", err)
	}
	sort.Slice(resources, func(i, j int) bool { return resources[i].ID < resources[j].ID })
	return Release{
		ID:             index.ReleaseID,
		IndexSHA256:    digestBytes(indexPayload),
		Model:          model,
		Resources:      resources,
		MCPCatalog:     catalog,
		MCPProjections: projections,
	}, nil
}

func loadBundle(
	root string,
	entry manifestEntry,
) (bundleManifest, installmodel.ComponentSpec, []Resource, error) {
	payload, err := readRegular(root, entry.Path)
	if err != nil {
		return bundleManifest{}, installmodel.ComponentSpec{}, nil,
			fmt.Errorf("read bundle manifest %q: %w", entry.Path, err)
	}
	if digestBytes(payload) != entry.SHA256 {
		return bundleManifest{}, installmodel.ComponentSpec{}, nil,
			fmt.Errorf("bundle manifest %q digest mismatch", entry.Path)
	}
	var manifest bundleManifest
	if err := decodeStrict(payload, &manifest); err != nil {
		return bundleManifest{}, installmodel.ComponentSpec{}, nil,
			fmt.Errorf("decode bundle manifest %q: %w", entry.Path, err)
	}
	if manifest.Component != entry.Component {
		return bundleManifest{}, installmodel.ComponentSpec{}, nil,
			fmt.Errorf("bundle manifest %q component mismatch", entry.Path)
	}
	sourceBase := path.Dir(entry.Path)
	bundleRoot := filepath.Join(root, filepath.FromSlash(sourceBase))
	component, resources, err := validateBundle(root, bundleRoot, sourceBase, manifest)
	if err != nil {
		return bundleManifest{}, installmodel.ComponentSpec{}, nil,
			fmt.Errorf("validate bundle %q: %w", entry.Component, err)
	}
	return manifest, component, resources, nil
}

func validateGlobal(manifests []bundleManifest) error {
	components := make(map[string]bool, len(manifests))
	identifiers := make(map[string]bool)
	for _, manifest := range manifests {
		if components[manifest.Component] {
			return fmt.Errorf("duplicate release component %q", manifest.Component)
		}
		components[manifest.Component] = true
		for _, unit := range manifest.InstallUnits {
			if identifiers[unit.ID] {
				return fmt.Errorf("duplicate release item %q", unit.ID)
			}
			identifiers[unit.ID] = true
		}
		for _, resource := range manifest.Resources {
			if identifiers[resource.ID] {
				return fmt.Errorf("duplicate release item %q", resource.ID)
			}
			identifiers[resource.ID] = true
		}
		for _, projection := range manifest.MCPProjections {
			if identifiers[projection.ID] {
				return fmt.Errorf("duplicate release item %q", projection.ID)
			}
			identifiers[projection.ID] = true
		}
	}
	for _, manifest := range manifests {
		for _, dependency := range manifest.Dependencies {
			if !components[dependency] {
				return fmt.Errorf("component %q has unknown dependency %q", manifest.Component, dependency)
			}
			if err := validateComponentDependency(
				domain.ComponentID(manifest.Component),
				domain.ComponentID(dependency),
			); err != nil {
				return err
			}
		}
	}
	return validateGlobalStructuredOwnership(manifests)
}
