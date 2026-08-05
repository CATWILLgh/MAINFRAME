package discovery

import (
	"errors"
	"fmt"
	"io/fs"
	"path"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

type Roots struct {
	Source  domain.ArtifactPath
	Targets map[domain.RootID]domain.ArtifactPath
}

type preparedRoots struct {
	source  domain.ArtifactPath
	targets map[domain.RootID]domain.ArtifactPath
}

type StableIdentityFS interface {
	fs.ReadLinkFS
	StableLinkIdentity(string, fs.FileInfo) (domain.LinkIdentity, error)
}

func Discover(model installmodel.Model, filesystem fs.ReadLinkFS, roots Roots) (domain.ObservedState, error) {
	return discover(model, filesystem, roots, nil)
}

func DiscoverWithOwnership(
	model installmodel.Model,
	filesystem fs.ReadLinkFS,
	roots Roots,
	registry linkownership.Registry,
) (domain.ObservedState, error) {
	return discover(model, filesystem, roots, &registry)
}

func discover(
	model installmodel.Model,
	filesystem fs.ReadLinkFS,
	roots Roots,
	registry *linkownership.Registry,
) (domain.ObservedState, error) {
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
	observedLocations := make(map[domain.Location]bool, len(artifacts))
	for _, spec := range artifacts {
		artifact, exists, err := inspectArtifact(filesystem, prepared, spec, registry)
		if err != nil {
			return domain.ObservedState{}, err
		}
		if exists {
			grouped[spec.ComponentID] = append(grouped[spec.ComponentID], artifact)
			observedLocations[spec.Target] = true
		}
	}
	if registry != nil {
		if err := inspectClaimOnlyArtifacts(
			filesystem, prepared, observedLocations, *registry, grouped,
		); err != nil {
			return domain.ObservedState{}, err
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
	registry *linkownership.Registry,
) (domain.Artifact, bool, error) {
	location := resolvedLocation(roots, spec.Target)
	info, err := filesystem.Lstat(location)
	if errors.Is(err, fs.ErrNotExist) {
		return domain.Artifact{}, false, nil
	}
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("inspect artifact %#v: %w", spec.Target, err)
	}
	if spec.Materialization == domain.MaterializationWritableFile {
		return inspectWritableFile(filesystem, spec, location, info, registry)
	}
	if info.Mode()&fs.ModeSymlink == 0 {
		if registry != nil {
			claim, claimed := registry.ClaimAt(spec.Target)
			if claimed && claim.ComponentID == spec.ComponentID && claim.UnitID == spec.UnitID {
				identity, err := stableLinkIdentity(filesystem, location, info)
				if err != nil {
					return domain.Artifact{}, false, err
				}
				return domain.Artifact{
					Location: spec.Target, UnitID: claim.UnitID,
					Ownership:  domain.OwnershipManagedDrifted,
					LinkDevice: identity.Device, LinkInode: identity.Inode,
					LinkBirthSeconds:     identity.BirthSeconds,
					LinkBirthNanoseconds: identity.BirthNanoseconds,
				}, true, nil
			}
		}
		ownership := domain.OwnershipConflict
		if spec.LegacyOnly {
			ownership = domain.OwnershipForeign
		}
		return observedArtifact(spec.Target, ownership), true, nil
	}
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	return inspectLink(filesystem, roots, spec, location, identity, registry)
}

func inspectLink(
	filesystem fs.ReadLinkFS,
	roots preparedRoots,
	spec installmodel.Artifact,
	location string,
	identity domain.LinkIdentity,
	registry *linkownership.Registry,
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
		ownership := classifyLegacy(spec, target)
		if registry == nil {
			return observedArtifact(spec.Target, ownership), true, nil
		}
		return observedLink(spec, ownership, rawTarget, identity), true, nil
	}
	ownership, err := classifyDesired(filesystem, roots, spec, target, rawTarget, registry)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	if registry == nil {
		return observedArtifact(spec.Target, ownership), true, nil
	}
	return observedLink(spec, ownership, rawTarget, identity), true, nil
}

func classifyDesired(
	filesystem fs.FS,
	roots preparedRoots,
	spec installmodel.Artifact,
	target string,
	rawTarget string,
	registry *linkownership.Registry,
) (domain.OwnershipStatus, error) {
	expected := path.Join(string(roots.source), string(spec.SourcePath))
	if registry != nil {
		claim, exists := registry.ClaimAt(spec.Target)
		if !exists {
			return classifyUnclaimed(filesystem, spec, target, expected)
		}
		if claim.ComponentID != spec.ComponentID || claim.UnitID != spec.UnitID {
			return domain.OwnershipConflict, nil
		}
		if claim.RawTarget != rawTarget {
			return domain.OwnershipManagedDrifted, nil
		}
		if target != expected {
			return domain.OwnershipManagedPrevious, nil
		}
		live, err := targetExists(filesystem, target)
		if err != nil {
			return "", fmt.Errorf("inspect link target %q: %w", target, err)
		}
		if live {
			return domain.OwnershipManagedExact, nil
		}
		return domain.OwnershipManagedPrevious, nil
	}
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

func classifyUnclaimed(
	filesystem fs.FS,
	spec installmodel.Artifact,
	target string,
	expected string,
) (domain.OwnershipStatus, error) {
	if target == expected {
		live, err := targetExists(filesystem, target)
		if err != nil {
			return "", fmt.Errorf("inspect unclaimed link target %q: %w", target, err)
		}
		if live {
			return domain.OwnershipExactAdoptable, nil
		}
		return domain.OwnershipForeign, nil
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

func observedLink(
	spec installmodel.Artifact,
	ownership domain.OwnershipStatus,
	rawTarget string,
	identity domain.LinkIdentity,
) domain.Artifact {
	return domain.Artifact{
		Location: spec.Target, UnitID: spec.UnitID, Ownership: ownership,
		RawTarget: rawTarget, LinkDevice: identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds:     identity.BirthSeconds,
		LinkBirthNanoseconds: identity.BirthNanoseconds,
	}
}

func stableLinkIdentity(
	filesystem fs.ReadLinkFS,
	name string,
	info fs.FileInfo,
) (domain.LinkIdentity, error) {
	if stable, ok := filesystem.(StableIdentityFS); ok {
		return stable.StableLinkIdentity(name, info)
	}
	return linkIdentity(info), nil
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
