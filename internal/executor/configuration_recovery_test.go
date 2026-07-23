package executor

import (
	"errors"
	"strings"
	"testing"
)

func TestRecoverConfigurationLifecycleStatesIsIdempotent(t *testing.T) {
	tests := []struct {
		name   string
		phase  StepPhase
		status TransactionStatus
	}{
		{name: "planned", phase: StepPrepared, status: TransactionInProgress},
		{name: "parent bound", phase: StepParentBound, status: TransactionInProgress},
		{name: "private created", phase: StepPrivateCreated, status: TransactionInProgress},
		{name: "staged", phase: StepStaged, status: TransactionInProgress},
		{name: "published", phase: StepPublished, status: TransactionInProgress},
		{name: "committed", phase: StepPublished, status: TransactionCommitted},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			configurations := newFakeConfigurationWorkspace(fixture.store)
			journal := configurationJournalFixture(test.phase, test.status)
			fixture.store.journal = &journal
			seedConfigurationRecoveryState(
				configurations,
				fixture.store.journal.Configurations[0].Mutations[0],
			)

			executor := fixture.configurationExecutor(configurations)
			if _, err := executor.Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}
			calls := len(configurations.calls)
			if _, err := executor.Recover(); err != nil {
				t.Fatalf("second Recover() error = %v", err)
			}
			if len(configurations.calls) != calls || fixture.store.journal != nil {
				t.Fatal("recovery retry repeated configuration work")
			}
		})
	}
}

func TestRecoverAdoptsPrivateDirectoryCreatedBeforeIdentitySave(t *testing.T) {
	fixture := newFixture(Preview{})
	configurations := newFakeConfigurationWorkspace(fixture.store)
	journal := configurationJournalFixture(
		StepParentBound,
		TransactionInProgress,
	)
	mutation := journal.Configurations[0].Mutations[0]
	configurations.private[mutation.Target] = FileIdentity{
		Device: 1,
		Inode:  9001,
	}
	fixture.store.journal = &journal

	if _, err := fixture.configurationExecutor(configurations).Recover(); err != nil {
		t.Fatalf("Recover() error = %v", err)
	}

	if configurations.private[mutation.Target] != (FileIdentity{}) {
		t.Fatal("recovery left an unrecorded private directory")
	}
	if !containsConfigurationCall(
		configurations.calls,
		"private:"+string(mutation.Target.Path),
	) {
		t.Fatalf("recovery did not adopt private directory: %#v", configurations.calls)
	}
}

func TestRecoverFinalizedConfigurationRemovesPrivateWorkspace(t *testing.T) {
	tests := []struct {
		name   string
		phase  StepPhase
		status TransactionStatus
	}{
		{
			name:   "rolled back",
			phase:  StepRolledBack,
			status: TransactionInProgress,
		},
		{
			name:   "committed",
			phase:  StepPublished,
			status: TransactionCommitted,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			configurations := newFakeConfigurationWorkspace(fixture.store)
			journal := configurationJournalFixture(test.phase, test.status)
			mutation := &journal.Configurations[0].Mutations[0]
			mutation.Finalized = true
			configurations.private[mutation.Target] = mutation.Private.Identity
			if test.status == TransactionCommitted {
				configurations.public[mutation.Target] = configurationState(
					mutation.After.SHA256,
					mutation.After.Mode,
					mutation.Parent,
					mutation.After.Entry,
				)
			}
			fixture.store.journal = &journal

			if _, err := fixture.configurationExecutor(configurations).Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}
			if configurations.private[mutation.Target] != (FileIdentity{}) {
				t.Fatal("recovery left a finalized private workspace")
			}
		})
	}
}

func TestRecoverKeepsEmptyPrivateUntilRollbackStateIsSaved(t *testing.T) {
	fixture := newFixture(Preview{})
	configurations := newFakeConfigurationWorkspace(fixture.store)
	journal := configurationJournalFixture(
		StepPrivateCreated,
		TransactionInProgress,
	)
	mutation := journal.Configurations[0].Mutations[0]
	configurations.private[mutation.Target] = mutation.Private.Identity
	fixture.store.journal = &journal
	fixture.store.saveFailAt = 1

	if _, err := fixture.configurationExecutor(configurations).Recover(); err == nil {
		t.Fatal("Recover() unexpectedly ignored rollback save failure")
	}
	if configurations.private[mutation.Target] == (FileIdentity{}) {
		t.Fatal("recovery removed private workspace before saving rollback")
	}

	fixture.store.saveFailAt = 0
	if _, err := fixture.configurationExecutor(configurations).Recover(); err != nil {
		t.Fatalf("retry Recover() error = %v", err)
	}
	if configurations.private[mutation.Target] != (FileIdentity{}) {
		t.Fatal("retry left private workspace")
	}
}

func TestRecoverRemovalDistinguishesPreRenameAndUnrecordedPublication(t *testing.T) {
	tests := []struct {
		name         string
		unrecorded   bool
		wantRollback bool
	}{
		{name: "pre-rename"},
		{name: "unrecorded publication", unrecorded: true, wantRollback: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			configurations := newFakeConfigurationWorkspace(fixture.store)
			journal := configurationRemovalJournalFixture(
				StepPrivateCreated,
				TransactionInProgress,
			)
			mutation := journal.Configurations[0].Mutations[0]
			before := configurationState(
				mutation.Before.SHA256,
				mutation.Before.Mode,
				mutation.Parent,
				mutation.Before.Entry,
			)
			configurations.private[mutation.Target] = mutation.Private.Identity
			if test.unrecorded {
				configurations.staged[mutation.Target] = before
				configurations.published[mutation.Target] = true
			} else {
				configurations.public[mutation.Target] = before
			}
			fixture.store.journal = &journal

			if _, err := fixture.configurationExecutor(configurations).Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}
			restored := configurations.public[mutation.Target]
			if restored != before {
				t.Fatalf("restored state = %#v, want %#v", restored, before)
			}
			gotRollback := containsConfigurationCall(
				configurations.calls,
				"rollback:"+string(mutation.Target.Path),
			)
			if gotRollback != test.wantRollback {
				t.Fatalf("rollback called = %v, calls = %#v", gotRollback, configurations.calls)
			}
		})
	}
}

func TestRecoverChecksPrivateModeOnlyBeforeCreatingConfigurationPrivate(t *testing.T) {
	tests := []struct {
		name       string
		phase      StepPhase
		wantChecks int
		wantError  bool
	}{
		{
			name:       "parent bound",
			phase:      StepParentBound,
			wantChecks: 1,
			wantError:  true,
		},
		{name: "private already created", phase: StepPrivateCreated},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(Preview{})
			configurations := newFakeConfigurationWorkspace(fixture.store)
			journal := configurationJournalFixture(
				test.phase,
				TransactionInProgress,
			)
			fixture.store.journal = &journal
			seedConfigurationRecoveryState(
				configurations,
				journal.Configurations[0].Mutations[0],
			)
			fixture.workspace.directoryModeErr = errors.New(
				"unsupported process umask",
			)

			_, err := fixture.configurationExecutor(configurations).Recover()

			if (err != nil) != test.wantError {
				t.Fatalf("Recover() error = %v", err)
			}
			if test.wantError && !strings.Contains(err.Error(), "unsupported process umask") {
				t.Fatalf("Recover() error = %v", err)
			}
			if fixture.workspace.directoryModeChecks != test.wantChecks {
				t.Fatalf(
					"directory mode checks = %d, want %d",
					fixture.workspace.directoryModeChecks,
					test.wantChecks,
				)
			}
			if test.wantError && (fixture.store.saveCalls != 0 ||
				len(configurations.calls) != 0) {
				t.Fatal("recovery private-mode preflight caused writes")
			}
		})
	}
}

func seedConfigurationRecoveryState(
	workspace *fakeConfigurationWorkspace,
	mutation JournalConfigurationMutation,
) {
	if mutation.Private.Identity != (FileIdentity{}) {
		workspace.private[mutation.Target] = mutation.Private.Identity
	}
	if mutation.StagedIdentity != (FileIdentity{}) {
		workspace.staged[mutation.Target] = configurationState(
			mutation.After.SHA256,
			mutation.After.Mode,
			mutation.Parent,
			mutation.StagedIdentity,
		)
	}
	if mutation.Phase == StepPublished {
		workspace.public[mutation.Target] = workspace.staged[mutation.Target]
		workspace.published[mutation.Target] = true
	}
}
