package executor

import (
	"errors"
	"path"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (workspace *fakeWorkspace) PlanDirectories(plan domain.Plan) (DirectoryPlan, error) {
	workspace.plannedOperations = append(
		[]domain.Operation(nil),
		plan.Operations...,
	)
	if workspace.directoryPlan != nil {
		return DirectoryPlan{
			Roots:   append([]RootSnapshot(nil), workspace.directoryPlan.Roots...),
			Missing: append([]DirectoryRequirement(nil), workspace.directoryPlan.Missing...),
		}, nil
	}
	seen := make(map[domain.RootID]bool)
	result := DirectoryPlan{}
	for _, operation := range plan.Operations {
		root := operation.Artifact.Location.Root
		if operation.Kind != domain.OperationInstall || seen[root] {
			continue
		}
		seen[root] = true
		result.Roots = append(result.Roots, RootSnapshot{
			Root:           root,
			AnchorPath:     "/home/user",
			AnchorIdentity: FileIdentity{Device: 1, Inode: 1},
			RootPath:       fakeRootPath(root),
		})
	}
	return result, nil
}

func (workspace *fakeWorkspace) CheckDirectoryMode(mode uint32) error {
	workspace.directoryModeChecks++
	if mode != ManagedDirectoryMode {
		return errors.New("unexpected managed directory mode")
	}
	return workspace.directoryModeErr
}

func fakeRootPath(root domain.RootID) string {
	if root == domain.RootHome {
		return ""
	}
	return "." + string(root)
}

func (workspace *fakeWorkspace) InspectDirectory(
	mutation DirectoryMutation,
) (DirectoryState, error) {
	workspace.directoryCalls = append(
		workspace.directoryCalls,
		"inspect:"+mutation.Target.Path,
	)
	if workspace.directoryInspectSave == 0 {
		workspace.directoryInspectSave = workspace.store.saveCalls
	}
	if state, exists := workspace.directories[mutation.Target]; exists {
		return state, nil
	}
	return DirectoryState{Parent: workspace.directoryParent(mutation)}, nil
}

func (workspace *fakeWorkspace) StageDirectory(
	mutation DirectoryMutation,
) (FileIdentity, error) {
	workspace.directoryCalls = append(
		workspace.directoryCalls,
		"stage:"+mutation.Target.Path,
	)
	if workspace.directoryStageSave == 0 {
		workspace.directoryStageSave = workspace.store.saveCalls
	}
	if identity := workspace.privateDirectories[mutation.PrivateName]; identity != (FileIdentity{}) {
		return identity, nil
	}
	workspace.nextInode++
	identity := FileIdentity{Device: 1, Inode: 300 + workspace.nextInode}
	workspace.privateDirectories[mutation.PrivateName] = identity
	return identity, nil
}

func (workspace *fakeWorkspace) PublishDirectory(
	mutation DirectoryMutation,
) (DirectoryState, error) {
	workspace.directoryCalls = append(
		workspace.directoryCalls,
		"publish:"+mutation.Target.Path,
	)
	if workspace.directoryPublishSave == 0 {
		workspace.directoryPublishSave = workspace.store.saveCalls
	}
	if state, exists := workspace.directories[mutation.Target]; exists {
		return state, nil
	}
	identity := workspace.privateDirectories[mutation.PrivateName]
	state := DirectoryState{
		Exists: true,
		Parent: mutation.Parent,
		Entry:  identity,
		Mode:   mutation.Mode,
	}
	workspace.directories[mutation.Target] = state
	delete(workspace.privateDirectories, mutation.PrivateName)
	return state, nil
}

func (workspace *fakeWorkspace) RollbackDirectory(mutation DirectoryMutation) error {
	workspace.directoryCalls = append(
		workspace.directoryCalls,
		"rollback:"+mutation.Target.Path,
	)
	if state, exists := workspace.directories[mutation.Target]; exists {
		if state.Entry != mutation.Entry {
			return errors.New("directory identity mismatch")
		}
		delete(workspace.directories, mutation.Target)
		workspace.privateDirectories[mutation.PrivateName] = mutation.Entry
	}
	return nil
}

func (workspace *fakeWorkspace) FinalizeDirectory(mutation DirectoryMutation) error {
	workspace.directoryCalls = append(
		workspace.directoryCalls,
		"finalize:"+mutation.Target.Path,
	)
	delete(workspace.privateDirectories, mutation.PrivateName)
	return nil
}

func (workspace *fakeWorkspace) directoryParent(
	mutation DirectoryMutation,
) FileIdentity {
	parentPath := path.Dir(mutation.Target.Path)
	if parentPath != "." {
		parent := DirectoryTarget{Root: mutation.Target.Root, Path: parentPath}
		if state, exists := workspace.directories[parent]; exists {
			return state.Entry
		}
	}
	return mutation.Root.AnchorIdentity
}
