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
	Home   domain.ArtifactPath
	Source domain.ArtifactPath
}

func Discover(model installmodel.Model, filesystem fs.ReadLinkFS, roots Roots) (domain.ObservedState, error) {
	if filesystem == nil {
		return domain.ObservedState{}, fmt.Errorf("filesystem must not be nil")
	}
	if err := validateRoots(roots); err != nil {
		return domain.ObservedState{}, err
	}
	grouped := make(map[domain.ComponentID][]domain.Artifact)
	for _, spec := range model.Artifacts() {
		artifact, exists, err := inspectArtifact(filesystem, roots, spec)
		if err != nil {
			return domain.ObservedState{}, err
		}
		if exists {
			grouped[spec.ComponentID] = append(grouped[spec.ComponentID], artifact)
		}
	}
	return observedState(grouped), nil
}

func inspectArtifact(
	filesystem fs.ReadLinkFS,
	roots Roots,
	spec installmodel.Artifact,
) (domain.Artifact, bool, error) {
	location := path.Join(string(roots.Home), string(spec.HomePath))
	info, err := filesystem.Lstat(location)
	if errors.Is(err, fs.ErrNotExist) {
		return domain.Artifact{}, false, nil
	}
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("inspect artifact %q: %w", spec.HomePath, err)
	}
	if info.Mode()&fs.ModeSymlink == 0 {
		return observedArtifact(spec.HomePath, domain.OwnershipConflict), true, nil
	}
	return inspectLink(filesystem, roots, spec, location)
}

func inspectLink(
	filesystem fs.ReadLinkFS,
	roots Roots,
	spec installmodel.Artifact,
	location string,
) (domain.Artifact, bool, error) {
	rawTarget, err := filesystem.ReadLink(location)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("read link %q: %w", spec.HomePath, err)
	}
	target, err := resolveTarget(location, rawTarget)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("resolve link %q: %w", spec.HomePath, err)
	}
	live, err := targetExists(filesystem, target)
	if err != nil {
		return domain.Artifact{}, false, fmt.Errorf("inspect link target %q: %w", target, err)
	}
	ownership := classifyLink(roots, spec, target, live)
	return observedArtifact(spec.HomePath, ownership), true, nil
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

func classifyLink(
	roots Roots,
	spec installmodel.Artifact,
	target string,
	live bool,
) domain.OwnershipStatus {
	expected := path.Join(string(roots.Source), string(spec.SourcePath))
	if target == expected {
		if live {
			return domain.OwnershipManagedExact
		}
		return domain.OwnershipManagedDrifted
	}
	for _, suffix := range spec.LegacyTargetSuffixes {
		if hasPathSuffix(target, string(suffix)) {
			return domain.OwnershipLegacyAdoptable
		}
	}
	return domain.OwnershipForeign
}

func hasPathSuffix(target, suffix string) bool {
	return target == suffix || strings.HasSuffix(target, "/"+suffix)
}

func observedArtifact(path domain.ArtifactPath, ownership domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{Path: path, Ownership: ownership}
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
		sort.Slice(artifacts, func(i, j int) bool { return artifacts[i].Path < artifacts[j].Path })
		components = append(components, domain.ObservedComponent{ID: id, Artifacts: artifacts})
	}
	return domain.ObservedState{Components: components}
}

func validateRoots(roots Roots) error {
	if !validRoot(roots.Home) {
		return fmt.Errorf("invalid home root %q", roots.Home)
	}
	if !validRoot(roots.Source) {
		return fmt.Errorf("invalid source root %q", roots.Source)
	}
	return nil
}

func validRoot(root domain.ArtifactPath) bool {
	return root.Valid() && fs.ValidPath(string(root))
}
