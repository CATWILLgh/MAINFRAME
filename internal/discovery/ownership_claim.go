package discovery

import (
	"errors"
	"fmt"
	"io/fs"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func inspectClaimOnlyArtifacts(
	filesystem fs.ReadLinkFS,
	roots preparedRoots,
	observedLocations map[domain.Location]bool,
	registry linkownership.Registry,
	grouped map[domain.ComponentID][]domain.Artifact,
) error {
	for _, claim := range registry.Claims() {
		if observedLocations[claim.Target] {
			continue
		}
		artifact, exists, err := inspectClaim(filesystem, roots, claim)
		if err != nil {
			return err
		}
		if exists {
			grouped[claim.ComponentID] = append(grouped[claim.ComponentID], artifact)
		}
	}
	return nil
}

func inspectClaim(
	filesystem fs.ReadLinkFS,
	roots preparedRoots,
	claim linkownership.Claim,
) (domain.Artifact, bool, error) {
	root, exists := roots.targets[claim.Target.Root]
	if !exists {
		return domain.Artifact{}, false, fmt.Errorf("missing target root %q", claim.Target.Root)
	}
	location := path.Join(string(root), string(claim.Target.Path))
	info, err := filesystem.Lstat(location)
	if errors.Is(err, fs.ErrNotExist) {
		return domain.Artifact{
			Location: claim.Target, UnitID: claim.UnitID,
			Ownership: domain.OwnershipManagedMissing, RawTarget: claim.RawTarget,
			Materialization: claim.Materialization,
			ContentSHA256:   claim.ContentSHA256, Mode: claim.Mode,
		}, true, nil
	}
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("inspect ownership claim %#v: %w", claim.Target, err)
	}
	if claim.Materialization == domain.MaterializationWritableFile {
		return inspectWritableClaim(filesystem, claim, location, info)
	}
	if info.Mode()&fs.ModeSymlink == 0 {
		identity, identityErr := stableLinkIdentity(filesystem, location, info)
		if identityErr != nil {
			return domain.Artifact{}, false, identityErr
		}
		return domain.Artifact{
			Location: claim.Target, UnitID: claim.UnitID,
			Ownership:  domain.OwnershipManagedDrifted,
			LinkDevice: identity.Device, LinkInode: identity.Inode,
			LinkBirthSeconds:     identity.BirthSeconds,
			LinkBirthNanoseconds: identity.BirthNanoseconds,
		}, true, nil
	}
	rawTarget, err := filesystem.ReadLink(location)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("read ownership claim %#v: %w", claim.Target, err)
	}
	status := domain.OwnershipManagedPrevious
	if rawTarget != claim.RawTarget {
		status = domain.OwnershipManagedDrifted
	}
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	return domain.Artifact{
		Location: claim.Target, UnitID: claim.UnitID, Ownership: status,
		RawTarget:  rawTarget,
		LinkDevice: identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds:     identity.BirthSeconds,
		LinkBirthNanoseconds: identity.BirthNanoseconds,
	}, true, nil
}
