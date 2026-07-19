package executor

import (
	"errors"
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Executor struct {
	locker         Locker
	store          JournalStore
	refresher      Refresher
	workspace      LinkWorkspace
	configurations ConfigurationWorkspace
	ownership      OwnershipStore
}

func New(
	locker Locker,
	store JournalStore,
	refresher Refresher,
	workspace LinkWorkspace,
) Executor {
	executor := Executor{
		locker: locker, store: store, refresher: refresher, workspace: workspace,
	}
	if ownership, ok := store.(OwnershipStore); ok {
		executor.ownership = ownership
	}
	return executor
}

func NewWithConfiguration(
	locker Locker,
	store JournalStore,
	refresher Refresher,
	workspace LinkWorkspace,
	configurations ConfigurationWorkspace,
) Executor {
	executor := New(locker, store, refresher, workspace)
	executor.configurations = configurations
	return executor
}

func (executor Executor) Apply(preview Preview) (Result, error) {
	return executor.withLock(func() (Result, error) {
		if _, err := executor.recoverLocked(); err != nil {
			return Result{}, fmt.Errorf("recover unfinished transaction: %w", err)
		}
		fresh, err := executor.refresher.Refresh(append([]domain.ComponentID(nil), preview.Desired...))
		if err != nil {
			return Result{}, fmt.Errorf("refresh preview: %w", err)
		}
		if !reflect.DeepEqual(preview, fresh) {
			return Result{}, errors.New("preview changed; review the fresh plan before applying")
		}
		if err := validatePreview(fresh); err != nil {
			return Result{}, err
		}
		return executor.execute(fresh)
	})
}

func (executor Executor) Recover() (Result, error) {
	return executor.withLock(executor.recoverLocked)
}

func (executor Executor) withLock(operation func() (Result, error)) (result Result, err error) {
	lock, err := executor.locker.Lock()
	if err != nil {
		return Result{}, fmt.Errorf("acquire transaction lock: %w", err)
	}
	defer func() {
		unlockErr := lock.Unlock()
		if unlockErr == nil {
			return
		}
		wrapped := fmt.Errorf("release transaction lock: %w", unlockErr)
		if err != nil {
			err = errors.Join(err, wrapped)
			return
		}
		result.Warnings = append(result.Warnings, wrapped.Error())
	}()
	return operation()
}

func (executor Executor) execute(preview Preview) (Result, error) {
	prepared, err := executor.materializeConfigurations(preview.Configuration)
	if err != nil {
		return Result{}, err
	}
	journal, err := executor.initializeJournal(preview, prepared)
	if err != nil {
		return Result{}, err
	}
	if err := executor.prepareConfigurations(&journal, prepared.payloads); err != nil {
		return Result{}, executor.abort(&journal, err)
	}
	for _, operation := range preview.Plan.Operations {
		mutation, err := executor.prepare(operation, preview.Release)
		if err != nil {
			return Result{}, executor.abort(&journal, fmt.Errorf("prepare mutation: %w", err))
		}
		journal.Steps = append(journal.Steps, mutation)
		if err := executor.store.Save(journal); err != nil {
			return Result{}, executor.abortAfterSaveFailure(
				&journal,
				fmt.Errorf("save allocated mutation: %w", err),
			)
		}
		index := len(journal.Steps) - 1
		if err := executor.executeStep(&journal, index); err != nil {
			return Result{}, executor.abort(&journal, err)
		}
	}
	if err := executor.publishConfigurations(&journal); err != nil {
		return Result{}, executor.abort(&journal, err)
	}
	if !hasMutations(journal) {
		return Result{}, nil
	}
	journal.Status = TransactionCommitted
	if err := executor.store.Save(journal); err != nil {
		return Result{}, fmt.Errorf(
			"commit transaction journal; recovery required: %w",
			err,
		)
	}
	if err := executor.finalizeCommitted(&journal); err != nil {
		return Result{}, fmt.Errorf("finalize committed transaction: %w", err)
	}
	if err := executor.store.Cleanup(); err != nil {
		return Result{Warnings: []string{fmt.Sprintf("cleanup committed journal: %v", err)}}, nil
	}
	return Result{}, nil
}

func (executor Executor) initializeJournal(
	preview Preview,
	prepared preparedConfigurations,
) (Journal, error) {
	directoryInput := directoryPlanningPlan(preview.Plan, prepared.targets)
	directoryPlan, err := executor.workspace.PlanDirectories(directoryInput)
	if err != nil {
		return Journal{}, fmt.Errorf("plan managed directories: %w", err)
	}
	if err := validateDirectoryPlan(
		preview.Plan,
		prepared.targets,
		directoryPlan,
	); err != nil {
		return Journal{}, fmt.Errorf("validate managed directories: %w", err)
	}
	if err := executor.checkDirectoryModes(
		directoryPlan.Missing,
		len(prepared.targets) > 0,
	); err != nil {
		return Journal{}, fmt.Errorf("check managed directory mode: %w", err)
	}
	journal := Journal{
		SchemaVersion: CurrentJournalSchemaVersion,
		Release:       preview.Release,
		Desired:       append([]domain.ComponentID(nil), preview.Desired...),
		Status:        TransactionInProgress,
		Plan: domain.Plan{
			Operations: append([]domain.Operation(nil), preview.Plan.Operations...),
		},
		Roots:          append([]RootSnapshot(nil), directoryPlan.Roots...),
		Configurations: cloneJournalConfigurations(prepared.transitions),
	}
	if err := executor.allocateDirectoryIntents(&journal, directoryPlan.Missing); err != nil {
		return Journal{}, fmt.Errorf("allocate managed directory: %w", err)
	}
	if len(journal.Configurations) > 0 || len(journal.Directories) > 0 {
		if err := executor.store.Save(journal); err != nil {
			return Journal{}, executor.abortAfterSaveFailure(
				&journal,
				fmt.Errorf("save managed directory intents: %w", err),
			)
		}
		for index := range journal.Directories {
			if err := executor.executeDirectory(&journal, index); err != nil {
				return Journal{}, executor.abort(&journal, err)
			}
		}
	}
	return journal, nil
}

func (executor Executor) checkDirectoryModes(
	requirements []DirectoryRequirement,
	configurationPrivate bool,
) error {
	checked := make(map[uint32]bool)
	if configurationPrivate {
		if err := executor.workspace.CheckDirectoryMode(ManagedDirectoryMode); err != nil {
			return err
		}
		checked[ManagedDirectoryMode] = true
	}
	for _, requirement := range requirements {
		if checked[requirement.Mode] {
			continue
		}
		if err := executor.workspace.CheckDirectoryMode(requirement.Mode); err != nil {
			return err
		}
		checked[requirement.Mode] = true
	}
	return nil
}

func hasMutations(journal Journal) bool {
	return len(journal.Configurations) > 0 ||
		len(journal.Directories) > 0 ||
		len(journal.Steps) > 0
}

func (executor Executor) executeStep(journal *Journal, index int) error {
	if claimOnlyMutation(journal.Steps[index].Kind) {
		return executor.publishClaim(journal, index)
	}
	if err := executor.preparePrivate(journal, index); err != nil {
		return fmt.Errorf("prepare private workspace: %w", err)
	}
	if journal.Steps[index].Kind == MutationInstall ||
		journal.Steps[index].Kind == MutationReplace {
		if err := executor.stageInstall(journal, index); err != nil {
			return fmt.Errorf("stage install: %w", err)
		}
	}
	step := &journal.Steps[index]
	actual, publishErr := executor.publish(*step)
	if err := confirmPublished(*step, actual); err != nil {
		return errors.Join(publishErr, fmt.Errorf("confirm publication: %w", err))
	}
	step.After = imageOf(actual)
	step.Phase = StepPublished
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(
			journal,
			errors.Join(publishErr, fmt.Errorf("save published mutation: %w", err)),
		)
	}
	if publishErr != nil {
		return fmt.Errorf("publish mutation: %w", publishErr)
	}
	return executor.publishClaim(journal, index)
}

func claimOnlyMutation(kind MutationKind) bool {
	return kind == MutationAdopt || kind == MutationRelinquish
}

func (executor Executor) preparePrivate(journal *Journal, index int) error {
	step := &journal.Steps[index]
	identity, err := executor.workspace.PreparePrivate(workspaceMutation(*step))
	if err != nil {
		return err
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a private directory without identity")
	}
	step.Private.Identity = identity
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save private directory identity: %w", err))
	}
	return nil
}

func (executor Executor) stageInstall(journal *Journal, index int) error {
	step := &journal.Steps[index]
	identity, err := executor.workspace.StageInstall(workspaceMutation(*step))
	if err != nil {
		return err
	}
	if !validFileIdentity(identity) {
		return errors.New("workspace returned a staged link without identity")
	}
	step.StagedIdentity = identity
	step.Phase = StepStaged
	if err := executor.store.Save(*journal); err != nil {
		return executor.persistBeforeAbort(journal, fmt.Errorf("save staged link identity: %w", err))
	}
	return nil
}

func (executor Executor) publish(step JournalMutation) (LinkState, error) {
	mutation := workspaceMutation(step)
	if step.Kind == MutationInstall {
		return executor.workspace.PublishInstall(mutation)
	}
	if step.Kind == MutationReplace {
		return executor.workspace.PublishReplace(mutation)
	}
	return executor.workspace.PublishRemove(mutation)
}

func confirmPublished(mutation JournalMutation, actual LinkState) error {
	expected := stateOf(mutation.After, mutation.Parent)
	if actual.Exists != expected.Exists ||
		actual.RawTarget != expected.RawTarget ||
		actual.Parent != expected.Parent {
		return errors.New("workspace returned an unexpected after-image")
	}
	if actual.Exists && !validFileIdentity(actual.Entry) {
		return errors.New("workspace returned an after-image without identity")
	}
	if (mutation.Kind == MutationInstall || mutation.Kind == MutationReplace) &&
		actual.Entry != mutation.StagedIdentity {
		return errors.New("published link identity differs from staged link")
	}
	if !actual.Exists && actual.Entry != (FileIdentity{}) {
		return errors.New("absent after-image has an identity")
	}
	return nil
}

func workspaceMutation(step JournalMutation) WorkspaceMutation {
	return WorkspaceMutation{
		Kind: step.Kind, Location: step.Location,
		SourceTarget: step.After.RawTarget,
		Before:       step.Before, After: step.After, Parent: step.Parent,
		Private: step.Private, StagedName: step.StagedName,
		StagedIdentity: step.StagedIdentity, RetainedName: step.RetainedName,
		Phase: step.Phase,
	}
}

func imageOf(state LinkState) LinkImage {
	return LinkImage{Exists: state.Exists, RawTarget: state.RawTarget, Entry: state.Entry}
}

func validFileIdentity(identity FileIdentity) bool {
	return identity.Device != 0 && identity.Inode != 0
}

func stateOf(image LinkImage, parent FileIdentity) LinkState {
	return LinkState{
		Exists: image.Exists, RawTarget: image.RawTarget,
		Parent: parent, Entry: image.Entry,
	}
}
