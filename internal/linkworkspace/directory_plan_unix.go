//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"path"
	"path/filepath"
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

type plannedDirectory struct {
	target   executor.DirectoryTarget
	physical string
}

func (workspace Workspace) PlanDirectories(
	plan domain.Plan,
) (executor.DirectoryPlan, error) {
	if err := workspace.rejectPhysicalTargetConflicts(plan); err != nil {
		return executor.DirectoryPlan{}, err
	}
	rootIDs := installRootIDs(plan)
	result := executor.DirectoryPlan{
		Roots: make([]executor.RootSnapshot, 0, len(rootIDs)),
	}
	for _, rootID := range rootIDs {
		root, exists, err := workspace.target(rootID)
		if err != nil {
			return executor.DirectoryPlan{}, err
		}
		if !exists {
			return executor.DirectoryPlan{}, fmt.Errorf("unknown target root %q", rootID)
		}
		result.Roots = append(result.Roots, root.snapshot(rootID))
	}
	directories, err := workspace.derivePlannedDirectories(plan)
	if err != nil {
		return executor.DirectoryPlan{}, err
	}
	sort.Slice(directories, func(left, right int) bool {
		leftDepth := strings.Count(directories[left].target.Path, "/")
		rightDepth := strings.Count(directories[right].target.Path, "/")
		if leftDepth != rightDepth {
			return leftDepth < rightDepth
		}
		return directories[left].physical < directories[right].physical
	})
	missing, err := workspace.missingDirectoryRequirements(directories)
	if err != nil {
		return executor.DirectoryPlan{}, err
	}
	result.Missing = missing
	return result, nil
}

func (workspace Workspace) missingDirectoryRequirements(
	directories []plannedDirectory,
) ([]executor.DirectoryRequirement, error) {
	missing := make(map[string]bool)
	result := make([]executor.DirectoryRequirement, 0, len(directories))
	for _, directory := range directories {
		if missing[filepath.Dir(directory.physical)] {
			missing[directory.physical] = true
		} else {
			root, found, err := workspace.target(directory.target.Root)
			if err != nil {
				return nil, err
			}
			if !found {
				return nil, fmt.Errorf(
					"unknown target root %q",
					directory.target.Root,
				)
			}
			exists, err := inspectPlannedDirectory(root, directory.target.Path)
			if err != nil {
				return nil, err
			}
			if exists {
				continue
			}
			missing[directory.physical] = true
		}
		result = append(result, executor.DirectoryRequirement{
			Target: directory.target,
			Mode:   executor.ManagedDirectoryMode,
		})
	}
	return result, nil
}

func installRootIDs(plan domain.Plan) []domain.RootID {
	seen := make(map[domain.RootID]bool)
	var roots []domain.RootID
	for _, operation := range plan.Operations {
		root := operation.Artifact.Location.Root
		if operation.Kind == domain.OperationInstall && !seen[root] {
			seen[root] = true
			roots = append(roots, root)
		}
	}
	sort.Slice(roots, func(left, right int) bool {
		return roots[left] < roots[right]
	})
	return roots
}

func (workspace Workspace) derivePlannedDirectories(
	plan domain.Plan,
) ([]plannedDirectory, error) {
	byPhysical := make(map[string]plannedDirectory)
	for _, operation := range plan.Operations {
		if operation.Kind != domain.OperationInstall {
			continue
		}
		root, exists, err := workspace.target(operation.Artifact.Location.Root)
		if err != nil {
			return nil, err
		}
		if !exists {
			continue
		}
		required := root.rootPath
		parent := path.Dir(string(operation.Artifact.Location.Path))
		if parent != "." {
			required = path.Join(required, parent)
		}
		for _, prefix := range portablePrefixes(required) {
			candidate := plannedDirectory{
				target: executor.DirectoryTarget{
					Root: operation.Artifact.Location.Root,
					Path: prefix,
				},
				physical: filepath.Join(root.anchor.path, filepath.FromSlash(prefix)),
			}
			current, exists := byPhysical[candidate.physical]
			if !exists || targetLess(candidate.target, current.target) {
				byPhysical[candidate.physical] = candidate
			}
		}
	}
	result := make([]plannedDirectory, 0, len(byPhysical))
	for _, directory := range byPhysical {
		result = append(result, directory)
	}
	return result, nil
}

func portablePrefixes(value string) []string {
	if value == "" {
		return nil
	}
	parts := strings.Split(value, "/")
	result := make([]string, 0, len(parts))
	for index := range parts {
		result = append(result, path.Join(parts[:index+1]...))
	}
	return result
}

func targetLess(
	left executor.DirectoryTarget,
	right executor.DirectoryTarget,
) bool {
	if left.Root != right.Root {
		return left.Root < right.Root
	}
	return left.Path < right.Path
}

func inspectPlannedDirectory(root managedRoot, relative string) (bool, error) {
	segments := strings.Split(relative, "/")
	anchorFD, err := root.anchor.open()
	if err != nil {
		return false, err
	}
	defer unix.Close(anchorFD)
	parentFD, err := openRelativeDirectory(anchorFD, segments[:len(segments)-1])
	if isMissing(err) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("open managed directory parent: %w", err)
	}
	defer unix.Close(parentFD)
	_, mode, err := identityAt(parentFD, segments[len(segments)-1])
	if isMissing(err) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("inspect managed directory: %w", err)
	}
	if fileType(mode) != unix.S_IFDIR {
		return false, errors.New("managed directory path is not a directory")
	}
	return true, nil
}

func (workspace Workspace) rejectPhysicalTargetConflicts(plan domain.Plan) error {
	physical := make([]string, 0, len(plan.Operations))
	for _, operation := range plan.Operations {
		root, exists, err := workspace.target(operation.Artifact.Location.Root)
		if err != nil {
			return err
		}
		if !exists {
			return fmt.Errorf("unknown target root %q", operation.Artifact.Location.Root)
		}
		target := filepath.Join(
			root.absolute(),
			filepath.FromSlash(string(operation.Artifact.Location.Path)),
		)
		for _, previous := range physical {
			if pathsOverlap(target, previous) {
				return fmt.Errorf("physical target paths overlap: %q and %q", previous, target)
			}
		}
		physical = append(physical, target)
	}
	return nil
}

func pathsOverlap(left, right string) bool {
	if left == right {
		return true
	}
	separator := string(filepath.Separator)
	return strings.HasPrefix(left, right+separator) ||
		strings.HasPrefix(right, left+separator)
}
