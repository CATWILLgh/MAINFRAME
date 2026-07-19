//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

const recoveryDigest = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

func TestRecoveryRestagesPreparedInstallAfterSourceDisappears(t *testing.T) {
	fixture := newWorkspaceFixture(t)
	location := fixture.location("mainframe")
	before := fixture.inspect(t, location)
	target := fixture.resolveSource(t, "bin/mainframe")
	privateName, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	plan := domain.Plan{Operations: []domain.Operation{{
		ComponentID: domain.ComponentCodex,
		Kind:        domain.OperationInstall,
		Artifact:    domain.Artifact{Location: location},
		SourcePath:  "bin/mainframe",
	}}}
	directories, err := fixture.workspace.PlanDirectories(plan)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	journal := recoveryJournal(plan, directories.Roots)
	journal.Steps = []executor.JournalMutation{{
		Kind:       executor.MutationInstall,
		Location:   location,
		SourcePath: "bin/mainframe",
		Before:     executor.LinkImage{},
		After: executor.LinkImage{
			Exists:    true,
			RawTarget: target,
		},
		Parent:     before.Parent,
		Private:    executor.PrivateDirectory{Name: privateName},
		StagedName: "staged",
		Phase:      executor.StepPrepared,
	}}
	stateRoot := filepath.Join(canonicalTempDir(t), "state")
	saveRecoveryJournal(t, stateRoot, journal)
	if err := os.RemoveAll(fixture.source); err != nil {
		t.Fatalf("remove release source: %v", err)
	}

	recoverTwice(t, stateRoot, map[domain.RootID]string{
		domain.RootUserBin: fixture.target,
	})

	if state := fixture.inspect(t, location); state.Exists {
		t.Fatalf("prepared install survived recovery: %#v", state)
	}
	assertPathMissing(t, filepath.Join(fixture.target, privateName))
}

func TestRecoveryRestoresZeroByteExchangeBeforeJournalSave(t *testing.T) {
	fixture := newConfigurationFixture(
		t,
		"config.toml",
		[]byte("before"),
		0o600,
	)
	mutation := fixture.preparedMutation(t, []byte{}, 0o600)
	beforeIdentity := mutation.Before.Entry
	fixture.prepareAndStage(t, &mutation, []byte{})
	published, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil {
		t.Fatalf("PublishConfiguration() error = %v", err)
	}
	if published.SHA256 != digestBytes(nil) {
		t.Fatalf("published zero-byte state = %#v", published)
	}
	rootPlan := recoveryPlan(fixture.location.Root)
	rootPlan.Operations[0].Artifact.Location = fixture.location
	directories, err := fixture.workspace.PlanDirectories(rootPlan)
	if err != nil {
		t.Fatalf("PlanDirectories() error = %v", err)
	}
	journal := recoveryJournal(domain.Plan{}, directories.Roots)
	journal.Configurations = []executor.JournalConfigurationTransition{{
		ResourceIDs: []string{"codex.mcp.context7"},
		Mutations:   []executor.JournalConfigurationMutation{mutation},
	}}
	stateRoot := filepath.Join(canonicalTempDir(t), "state")
	saveRecoveryJournal(t, stateRoot, journal)
	if err := os.RemoveAll(fixture.workspace.source.path); err != nil {
		t.Fatalf("remove release source: %v", err)
	}

	recoverTwice(t, stateRoot, map[domain.RootID]string{
		fixture.location.Root: fixture.target,
	})

	restored := fixture.inspect(t)
	assertConfigurationState(t, restored, []byte("before"), 0o600)
	if restored.Entry != beforeIdentity {
		t.Fatalf("restored identity = %#v, want %#v", restored.Entry, beforeIdentity)
	}
	assertPathMissing(t, filepath.Join(fixture.target, mutation.Private.Name))
}

func recoveryJournal(
	plan domain.Plan,
	roots []executor.RootSnapshot,
) executor.Journal {
	return executor.Journal{
		SchemaVersion: executor.CurrentJournalSchemaVersion,
		Release: executor.ReleaseIdentity{
			ID:          "release",
			IndexSHA256: recoveryDigest,
		},
		Desired:        []domain.ComponentID{domain.ComponentCodex},
		Status:         executor.TransactionInProgress,
		Plan:           plan,
		Roots:          append([]executor.RootSnapshot(nil), roots...),
		Configurations: []executor.JournalConfigurationTransition{},
		Directories:    []executor.JournalDirectory{},
		Steps:          []executor.JournalMutation{},
	}
}

func saveRecoveryJournal(
	t *testing.T,
	stateRoot string,
	journal executor.Journal,
) {
	t.Helper()
	state, err := executor.OpenUnixState(stateRoot)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	if err := state.Save(journal); err != nil {
		state.Close()
		t.Fatalf("Save() error = %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}
}

func recoverTwice(
	t *testing.T,
	stateRoot string,
	targets map[domain.RootID]string,
) {
	t.Helper()
	workspace, err := NewRecovery(targets)
	if err != nil {
		t.Fatalf("NewRecovery() error = %v", err)
	}
	state, err := executor.OpenUnixState(stateRoot)
	if err != nil {
		t.Fatalf("OpenUnixState() error = %v", err)
	}
	defer state.Close()
	runner := executor.NewWithConfiguration(
		state,
		state,
		nil,
		workspace,
		workspace,
	)
	for attempt := 1; attempt <= 2; attempt++ {
		if _, err := runner.Recover(); err != nil {
			t.Fatalf("Recover() attempt %d error = %v", attempt, err)
		}
	}
	journal, err := state.Load()
	if err != nil || journal != nil {
		t.Fatalf("Load() after recovery = %#v, %v", journal, err)
	}
}

func assertPathMissing(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Lstat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("path %q remains: %v", path, err)
	}
}
