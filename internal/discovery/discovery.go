package discovery

import (
	"errors"
	"fmt"
	"io/fs"
	"path"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

type Roots struct {
	Source  domain.ArtifactPath
	Targets map[domain.RootID]domain.ArtifactPath
}

type preparedRoots struct {
	source  domain.ArtifactPath
	targets map[domain.RootID]domain.ArtifactPath
}

func Discover(model installmodel.Model, filesystem fs.ReadLinkFS, roots Roots) (domain.ObservedState, error) {
	if filesystem == nil {
		return domain.ObservedState{}, fmt.Errorf("filesystem must not be nil")
	}
	artifacts := model.Artifacts()
	prepared, err := prepareRoots(roots, artifacts)
	if err != nil {
		return domain.ObservedState{}, err
	}
	if err := validateResolvedLocations(prepared, artifacts); err != nil {
		return domain.ObservedState{}, err
	}
	grouped := make(map[domain.ComponentID][]domain.Artifact)
	for _, spec := range artifacts {
		artifact, exists, err := inspectArtifact(filesystem, prepared, spec)
		if err != nil {
			return domain.ObservedState{}, err
		}
		if exists {
			grouped[spec.ComponentID] = append(grouped[spec.ComponentID], artifact)
		}
	}
	return observedState(grouped), nil
}

func prepareRoots(roots Roots, artifacts []installmodel.Artifact) (preparedRoots, error) {
	if !validPath(roots.Source) {
		return preparedRoots{}, fmt.Errorf("invalid source root %q", roots.Source)
	}
	targets := make(map[domain.RootID]domain.ArtifactPath, len(roots.Targets))
	for root, target := range roots.Targets {
		if !root.Valid() {
			return preparedRoots{}, fmt.Errorf("invalid root ID %q", root)
		}
		if !validPath(target) {
			return preparedRoots{}, fmt.Errorf("invalid target root %q for %q", target, root)
		}
		targets[root] = target
	}
	for _, artifact := range artifacts {
		if _, exists := targets[artifact.Target.Root]; !exists {
			return preparedRoots{}, fmt.Errorf("missing target root %q", artifact.Target.Root)
		}
	}
	return preparedRoots{source: roots.Source, targets: targets}, nil
}

func validateResolvedLocations(roots preparedRoots, artifacts []installmodel.Artifact) error {
	for i := range artifacts {
		left := artifacts[i]
		leftPath := resolvedLocation(roots, left.Target)
		for j := 0; j < i; j++ {
			right := artifacts[j]
			if left.Target.Root == right.Target.Root {
				continue
			}
			rightPath := resolvedLocation(roots, right.Target)
			if pathsOverlap(leftPath, rightPath) {
				return fmt.Errorf("resolved artifact locations %q and %q collide", leftPath, rightPath)
			}
		}
	}
	return nil
}

func inspectArtifact(
	filesystem fs.ReadLinkFS,
	roots preparedRoots,
	spec installmodel.Artifact,
) (domain.Artifact, bool, error) {
	location := resolvedLocation(roots, spec.Target)
	info, err := filesystem.Lstat(location)
	if errors.Is(err, fs.ErrNotExist) {
		return domain.Artifact{}, false, nil
	}
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("inspect artifact %#v: %w", spec.Target, err)
	}
	if info.Mode()&fs.ModeSymlink == 0 {
		ownership := domain.OwnershipConflict
		if spec.LegacyOnly {
			ownership = domain.OwnershipForeign
		}
		return observedArtifact(spec.Target, ownership), true, nil
	}
	return inspectLink(filesystem, roots, spec, location)
}

func inspectLink(
	filesystem fs.ReadLinkFS,
	roots preparedRoots,
	spec installmodel.Artifact,
	location string,
) (domain.Artifact, bool, error) {
	rawTarget, err := filesystem.ReadLink(location)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("read link %#v: %w", spec.Target, err)
	}
	target, err := resolveTarget(location, rawTarget)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("resolve link %#v: %w", spec.Target, err)
	}
	if spec.LegacyOnly {
		return observedArtifact(spec.Target, classifyLegacy(spec, target)), true, nil
	}
	ownership, err := classifyDesired(filesystem, roots, spec, target)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	return observedArtifact(spec.Target, ownership), true, nil
}

func classifyDesired(
	filesystem fs.FS,
	roots preparedRoots,
	spec installmodel.Artifact,
	target string,
) (domain.OwnershipStatus, error) {
	expected := path.Join(string(roots.source), string(spec.SourcePath))
	if target == expected {
		live, err := targetExists(filesystem, target)
		if err != nil {
			return "", fmt.Errorf("inspect link target %q: %w", target, err)
		}
		if live {
			return domain.OwnershipManagedExact, nil
		}
		return domain.OwnershipManagedDrifted, nil
	}
	if matchesSuffix(target, spec.LegacyTargetSuffixes) {
		return domain.OwnershipLegacyAdoptable, nil
	}
	return domain.OwnershipForeign, nil
}

func classifyLegacy(spec installmodel.Artifact, target string) domain.OwnershipStatus {
	if matchesSuffix(target, spec.LegacyTargetSuffixes) {
		return domain.OwnershipLegacyAdoptable
	}
	return domain.OwnershipForeign
}

func resolveTarget(linkLocation, rawTarget string) (string, error) {
	if rawTarget == "" {
		return "", fmt.Errorf("empty target")
	}
	var target string
	if path.IsAbs(rawTarget) {
		target = strings.TrimPrefix(path.Clean(rawTarget), "/")
	} else {
		target = path.Clean(path.Join(path.Dir(linkLocation), rawTarget))
	}
	if target == "." || !fs.ValidPath(target) {
		return "", fmt.Errorf("target %q escapes the filesystem root", rawTarget)
	}
	return target, nil
}

func targetExists(filesystem fs.FS, target string) (bool, error) {
	_, err := fs.Stat(filesystem, target)
	if errors.Is(err, fs.ErrNotExist) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

func matchesSuffix(target string, suffixes []domain.ArtifactPath) bool {
	for _, suffix := range suffixes {
		value := string(suffix)
		if target == value || strings.HasSuffix(target, "/"+value) {
			return true
		}
	}
	return false
}

func observedArtifact(location domain.Location, ownership domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{Location: location, Ownership: ownership}
}

func observedState(grouped map[domain.ComponentID][]domain.Artifact) domain.ObservedState {
	ids := make([]domain.ComponentID, 0, len(grouped))
	for id := range grouped {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	components := make([]domain.ObservedComponent, 0, len(ids))
	for _, id := range ids {
		artifacts := grouped[id]
		sort.Slice(artifacts, func(i, j int) bool {
			if artifacts[i].Location.Root != artifacts[j].Location.Root {
				return artifacts[i].Location.Root < artifacts[j].Location.Root
			}
			return artifacts[i].Location.Path < artifacts[j].Location.Path
		})
		components = append(components, domain.ObservedComponent{ID: id, Artifacts: artifacts})
	}
	return domain.ObservedState{Components: components}
}

func validPath(artifactPath domain.ArtifactPath) bool {
	return artifactPath.Valid() && fs.ValidPath(string(artifactPath))
}

func resolvedLocation(roots preparedRoots, location domain.Location) string {
	return path.Join(string(roots.targets[location.Root]), string(location.Path))
}

func pathsOverlap(left, right string) bool {
	return left == right || strings.HasPrefix(left, right+"/") || strings.HasPrefix(right, left+"/")
}
