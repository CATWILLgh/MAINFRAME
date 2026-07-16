package executor

import (
	"fmt"
	"path"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type allowedDirectory struct {
	Target DirectoryTarget
	Path   string
}

func validateDirectoryPlan(plan domain.Plan, directoryPlan DirectoryPlan) error {
	directories := make([]JournalDirectory, 0, len(directoryPlan.Missing))
	for index, requirement := range directoryPlan.Missing {
		directories = append(directories, JournalDirectory{
			Target:      requirement.Target,
			Mode:        requirement.Mode,
			PrivateName: fmt.Sprintf(".mainframe-%032x", index+1),
			Phase:       StepPrepared,
		})
	}
	return validateJournalDirectories(Journal{
		Status:      TransactionInProgress,
		Plan:        plan,
		Roots:       directoryPlan.Roots,
		Directories: directories,
	})
}

func validateJournalDirectories(journal Journal) error {
	roots, err := validateRootSnapshots(journal.Plan, journal.Roots)
	if err != nil {
		return err
	}
	allowed := deriveAllowedDirectories(journal.Plan, roots)
	indexes := make(map[string]int)
	privateNames := make(map[string]bool)
	for index, directory := range journal.Directories {
		physical, err := validateJournalDirectory(directory, roots, allowed)
		if err != nil {
			return fmt.Errorf("invalid directory %d: %w", index, err)
		}
		if previous, exists := indexes[physical]; exists {
			return fmt.Errorf("directories %d and %d target the same path", previous, index)
		}
		indexes[physical] = index
		if privateNames[directory.PrivateName] {
			return fmt.Errorf("duplicate directory private name %q", directory.PrivateName)
		}
		privateNames[directory.PrivateName] = true
		if journal.Status == TransactionCommitted && directory.Phase != StepPublished {
			return fmt.Errorf("committed transaction has non-applied directory %d", index)
		}
	}
	for physical, index := range indexes {
		if parentIndex, exists := indexes[filepath.Dir(physical)]; exists && parentIndex > index {
			return fmt.Errorf("directory %d appears before its managed parent", index)
		}
	}
	return nil
}

func validateRootSnapshots(
	plan domain.Plan,
	snapshots []RootSnapshot,
) (map[domain.RootID]RootSnapshot, error) {
	required := make(map[domain.RootID]bool)
	for _, operation := range plan.Operations {
		if operation.Kind == domain.OperationInstall {
			required[operation.Artifact.Location.Root] = true
		}
	}
	roots := make(map[domain.RootID]RootSnapshot)
	for index, snapshot := range snapshots {
		if !required[snapshot.Root] || roots[snapshot.Root].Root != "" {
			return nil, fmt.Errorf("invalid root snapshot %d", index)
		}
		if !validAnchorPath(snapshot.AnchorPath) ||
			!validFileIdentity(snapshot.AnchorIdentity) ||
			snapshot.RootPath != "" && !validRelative(snapshot.RootPath) {
			return nil, fmt.Errorf("invalid root snapshot %d", index)
		}
		roots[snapshot.Root] = snapshot
	}
	if len(roots) != len(required) {
		return nil, fmt.Errorf("root snapshots do not match install roots")
	}
	return roots, nil
}

func validAnchorPath(value string) bool {
	return validText(value) && filepath.IsAbs(value) && filepath.Clean(value) == value
}

func deriveAllowedDirectories(
	plan domain.Plan,
	roots map[domain.RootID]RootSnapshot,
) map[string]allowedDirectory {
	allowed := make(map[string]allowedDirectory)
	for _, operation := range plan.Operations {
		if operation.Kind != domain.OperationInstall {
			continue
		}
		root := roots[operation.Artifact.Location.Root]
		required := root.RootPath
		parent := path.Dir(string(operation.Artifact.Location.Path))
		if parent != "." {
			required = path.Join(required, parent)
		}
		for _, prefix := range pathPrefixes(required) {
			target := DirectoryTarget{Root: root.Root, Path: prefix}
			physical := physicalDirectory(root, prefix)
			candidate := allowedDirectory{Target: target, Path: physical}
			current, exists := allowed[physical]
			if !exists || directoryTargetLess(candidate.Target, current.Target) {
				allowed[physical] = candidate
			}
		}
	}
	return allowed
}

func pathPrefixes(value string) []string {
	if value == "" {
		return nil
	}
	parts := strings.Split(value, "/")
	prefixes := make([]string, 0, len(parts))
	for index := range parts {
		prefixes = append(prefixes, path.Join(parts[:index+1]...))
	}
	return prefixes
}

func directoryTargetLess(left, right DirectoryTarget) bool {
	if left.Root != right.Root {
		return left.Root < right.Root
	}
	return left.Path < right.Path
}

func validateJournalDirectory(
	directory JournalDirectory,
	roots map[domain.RootID]RootSnapshot,
	allowed map[string]allowedDirectory,
) (string, error) {
	root, exists := roots[directory.Target.Root]
	if !exists || !validRelative(directory.Target.Path) {
		return "", fmt.Errorf("invalid target")
	}
	physical := physicalDirectory(root, directory.Target.Path)
	requirement, exists := allowed[physical]
	if !exists || requirement.Target != directory.Target {
		return "", fmt.Errorf("target was not derived from the saved plan")
	}
	if directory.Mode != ManagedDirectoryMode {
		return "", fmt.Errorf("invalid mode %#o", directory.Mode)
	}
	if !privateNamePattern.MatchString(directory.PrivateName) {
		return "", fmt.Errorf("invalid private name")
	}
	if err := validateDirectoryPhase(directory); err != nil {
		return "", err
	}
	return physical, nil
}

func physicalDirectory(root RootSnapshot, relative string) string {
	return filepath.Clean(filepath.Join(root.AnchorPath, filepath.FromSlash(relative)))
}

func validateDirectoryPhase(directory JournalDirectory) error {
	if !validStepPhase(directory.Phase) {
		return fmt.Errorf("invalid phase %q", directory.Phase)
	}
	if directory.Finalized &&
		directory.Phase != StepPublished && directory.Phase != StepRolledBack {
		return fmt.Errorf("invalid finalized phase")
	}
	if directory.Phase == StepPrepared {
		if directory.Entry != (FileIdentity{}) ||
			directory.Parent != (FileIdentity{}) &&
				!validFileIdentity(directory.Parent) {
			return fmt.Errorf("invalid prepared identities")
		}
		return nil
	}
	if directory.Phase == StepRolledBack &&
		directory.Finalized &&
		directory.Parent == (FileIdentity{}) &&
		directory.Entry == (FileIdentity{}) {
		return nil
	}
	if !validFileIdentity(directory.Parent) || !validFileIdentity(directory.Entry) {
		return fmt.Errorf("missing directory identity")
	}
	return nil
}
