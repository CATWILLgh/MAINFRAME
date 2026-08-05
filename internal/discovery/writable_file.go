package discovery

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func inspectWritableFile(
	filesystem fs.ReadLinkFS,
	spec installmodel.Artifact,
	location string,
	info fs.FileInfo,
	registry *linkownership.Registry,
) (domain.Artifact, bool, error) {
	if info.Mode()&fs.ModeSymlink != 0 {
		return inspectWritableFileMigration(filesystem, spec, location, info, registry)
	}
	if !info.Mode().IsRegular() {
		return observedArtifact(spec.Target, domain.OwnershipConflict), true, nil
	}
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	mode := uint32(info.Mode().Perm())
	if registry == nil {
		return observedWritable(spec, domain.OwnershipConflict, "", mode, identity), true, nil
	}
	claim, exists := registry.ClaimAt(spec.Target)
	if !exists || claim.ComponentID != spec.ComponentID || claim.UnitID != spec.UnitID ||
		claim.Materialization != domain.MaterializationWritableFile {
		return observedWritable(spec, domain.OwnershipConflict, "", mode, identity), true, nil
	}
	if mode != claim.Mode {
		return observedWritable(spec, domain.OwnershipManagedDrifted, "", mode, identity), true, nil
	}
	digest, err := regularFileDigest(filesystem, location)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("hash writable file %#v: %w", spec.Target, err)
	}
	status := classifyWritableFile(spec, digest, mode, claim)
	return observedWritable(spec, status, digest, mode, identity), true, nil
}

func inspectWritableFileMigration(
	filesystem fs.ReadLinkFS,
	spec installmodel.Artifact,
	location string,
	info fs.FileInfo,
	registry *linkownership.Registry,
) (domain.Artifact, bool, error) {
	rawTarget, err := filesystem.ReadLink(location)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("read managed migration link %#v: %w", spec.Target, err)
	}
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	status := domain.OwnershipConflict
	if registry != nil {
		claim, exists := registry.ClaimAt(spec.Target)
		if exists && claim.ComponentID == spec.ComponentID && claim.UnitID == spec.UnitID &&
			claim.Materialization != domain.MaterializationWritableFile && claim.RawTarget == rawTarget {
			status = domain.OwnershipManagedPrevious
		}
	}
	return domain.Artifact{
		Location: spec.Target, UnitID: spec.UnitID, Ownership: status,
		RawTarget: rawTarget, LinkDevice: identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds: identity.BirthSeconds, LinkBirthNanoseconds: identity.BirthNanoseconds,
	}, true, nil
}

func classifyWritableFile(
	spec installmodel.Artifact,
	digest string,
	mode uint32,
	claim linkownership.Claim,
) domain.OwnershipStatus {
	if digest != claim.ContentSHA256 || mode != claim.Mode {
		return domain.OwnershipManagedDrifted
	}
	if digest == spec.SourceSHA256 && mode == 0o600 {
		return domain.OwnershipManagedExact
	}
	return domain.OwnershipManagedPrevious
}

func regularFileDigest(filesystem fs.FS, name string) (string, error) {
	file, err := filesystem.Open(name)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func observedWritable(
	spec installmodel.Artifact,
	ownership domain.OwnershipStatus,
	digest string,
	mode uint32,
	identity domain.LinkIdentity,
) domain.Artifact {
	return domain.Artifact{
		Location: spec.Target, UnitID: spec.UnitID, Ownership: ownership,
		Materialization: domain.MaterializationWritableFile,
		ContentSHA256:   digest, Mode: mode,
		LinkDevice: identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds: identity.BirthSeconds, LinkBirthNanoseconds: identity.BirthNanoseconds,
	}
}

func inspectWritableClaim(
	filesystem fs.ReadLinkFS,
	claim linkownership.Claim,
	location string,
	info fs.FileInfo,
) (domain.Artifact, bool, error) {
	if !info.Mode().IsRegular() {
		return observedClaimedDrift(claim, info, filesystem, location)
	}
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	mode := uint32(info.Mode().Perm())
	if mode != claim.Mode {
		return domain.Artifact{
			Location: claim.Target, UnitID: claim.UnitID,
			Ownership:       domain.OwnershipManagedDrifted,
			Materialization: claim.Materialization, Mode: mode,
			LinkDevice: identity.Device, LinkInode: identity.Inode,
			LinkBirthSeconds: identity.BirthSeconds, LinkBirthNanoseconds: identity.BirthNanoseconds,
		}, true, nil
	}
	digest, err := regularFileDigest(filesystem, location)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	status := domain.OwnershipManagedPrevious
	if digest != claim.ContentSHA256 {
		status = domain.OwnershipManagedDrifted
	}
	return domain.Artifact{
		Location: claim.Target, UnitID: claim.UnitID, Ownership: status,
		Materialization: claim.Materialization, ContentSHA256: digest, Mode: mode,
		LinkDevice: identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds: identity.BirthSeconds, LinkBirthNanoseconds: identity.BirthNanoseconds,
	}, true, nil
}

func observedClaimedDrift(
	claim linkownership.Claim,
	info fs.FileInfo,
	filesystem fs.ReadLinkFS,
	location string,
) (domain.Artifact, bool, error) {
	identity, err := stableLinkIdentity(filesystem, location, info)
	if err != nil {
		return domain.Artifact{}, false, err
	}
	return domain.Artifact{
		Location: claim.Target, UnitID: claim.UnitID,
		Ownership:       domain.OwnershipManagedDrifted,
		Materialization: claim.Materialization,
		LinkDevice:      identity.Device, LinkInode: identity.Inode,
		LinkBirthSeconds: identity.BirthSeconds, LinkBirthNanoseconds: identity.BirthNanoseconds,
	}, true, nil
}
