package executor

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestApplyRejectsStalePreparedConfigurationBeforeWrites(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	fresh := preparedExecutorPreview(t, `{"bash":"deny"}`)
	fixture := newFixture(fresh)
	configurations := newFakeConfigurationWorkspace(fixture.store)

	_, err := NewWithConfiguration(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
	).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "preview changed") {
		t.Fatalf("Apply() error = %v", err)
	}
	if len(fixture.store.saves) != 0 || len(configurations.calls) != 0 ||
		fixture.workspace.writeCount() != 0 {
		t.Fatal("stale prepared configuration caused writes")
	}
}

func TestApplyRequiresConfigurationWorkspaceBeforeWrites(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	fixture := newFixture(preview)

	_, err := fixture.executor().Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "configuration workspace") {
		t.Fatalf("Apply() error = %v", err)
	}
	if len(fixture.store.saves) != 0 || fixture.workspace.writeCount() != 0 {
		t.Fatal("missing configuration workspace caused writes")
	}
}

func TestApplyChecksPrivateModeBeforeConfigurationIntent(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	fixture.workspace.directoryModeErr = errors.New("unsupported process umask")

	_, err := fixture.configurationExecutor(configurations).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "unsupported process umask") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.directoryModeChecks != 1 {
		t.Fatalf(
			"directory mode checks = %d, want 1",
			fixture.workspace.directoryModeChecks,
		)
	}
	if fixture.store.saveCalls != 0 || len(configurations.calls) != 0 ||
		fixture.workspace.writeCount() != 0 {
		t.Fatal("configuration private-mode preflight caused writes")
	}
}

func TestApplyStagesAllConfigurationsBeforeLinksAndPublishesInOrder(t *testing.T) {
	preview := preparedExecutorPreview(
		t,
		`{"bash":"allow"}`,
		install("link", "source/link"),
	)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)

	_, err := fixture.configurationExecutor(configurations).Apply(preview)

	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	assertConfigurationCallOrder(t, configurations.calls, []string{
		"inspect:opencode.json",
		"inspect:opencode.json.mainframe-permissions.json",
		"private:opencode.json",
		"private:opencode.json.mainframe-permissions.json",
		"capability:opencode.json",
		"capability:opencode.json.mainframe-permissions.json",
		"stage:opencode.json",
		"stage:opencode.json.mainframe-permissions.json",
		"publish:opencode.json",
		"publish:opencode.json.mainframe-permissions.json",
		"finalize:opencode.json",
		"finalize-private:opencode.json",
		"finalize:opencode.json.mainframe-permissions.json",
		"finalize-private:opencode.json.mainframe-permissions.json",
	})
	if configurations.firstPublishLinkWrites != 1 {
		t.Fatalf("link writes before configuration publish = %d, want 1",
			configurations.firstPublishLinkWrites)
	}
	if configurations.firstCallSave["inspect"] == 0 {
		t.Fatal("configuration was inspected before its journal intent was saved")
	}
	if len(fixture.workspace.plannedOperations) != 3 {
		t.Fatalf(
			"directory planning operations = %#v",
			fixture.workspace.plannedOperations,
		)
	}
	for _, saved := range fixture.store.saves {
		if journalContainsConfigurationBytes(saved, configurations.payloads) {
			t.Fatal("saved journal contains configuration bytes")
		}
	}
}

func TestApplyInfersUncertainConfigurationPublication(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	configurations.failCall = "publish"
	configurations.failAfterWrite = true

	_, err := fixture.configurationExecutor(configurations).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "publish configuration") {
		t.Fatalf("Apply() error = %v", err)
	}
	if len(configurations.published) != 0 {
		t.Fatal("uncertain publication was not inferred and rolled back")
	}
	if !reverseRollbackOrder(configurations.calls) {
		t.Fatalf("rollback order = %#v", configurations.calls)
	}
}

func TestApplyNeverRollsBackAfterConfigurationCommitSaveAttempt(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	tests := []struct {
		name             string
		failAfterWrite   bool
		wantAfterRecover bool
	}{
		{name: "commit not persisted"},
		{
			name:             "commit persisted despite error",
			failAfterWrite:   true,
			wantAfterRecover: true,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			fixture := newFixture(preview)
			configurations := newFakeConfigurationWorkspace(fixture.store)
			if test.failAfterWrite {
				fixture.store.saveFailAfterWriteAt = 10
			} else {
				fixture.store.saveFailAt = 10
			}

			_, err := fixture.configurationExecutor(configurations).Apply(preview)

			if err == nil || len(configurations.published) != 2 {
				t.Fatalf(
					"commit uncertainty rolled back: error=%v published=%v",
					err,
					configurations.published,
				)
			}
			fixture.store.saveFailAt = 0
			fixture.store.saveFailAfterWriteAt = 0
			if _, err := fixture.configurationExecutor(configurations).Recover(); err != nil {
				t.Fatalf("Recover() error = %v", err)
			}
			if (len(configurations.public) == 2) != test.wantAfterRecover {
				t.Fatalf("recovered public configurations = %#v", configurations.public)
			}
		})
	}
}

func TestApplyConfigurationSaveFailuresRollbackReverseBeforeLinks(t *testing.T) {
	preview := preparedExecutorPreview(t, `{"bash":"allow"}`)
	for failedSave := 1; failedSave <= 9; failedSave++ {
		t.Run(string(rune('0'+failedSave)), func(t *testing.T) {
			fixture := newFixture(preview)
			configurations := newFakeConfigurationWorkspace(fixture.store)
			fixture.store.saveFailAt = failedSave

			_, err := fixture.configurationExecutor(configurations).Apply(preview)

			if err == nil {
				t.Fatalf("save %d unexpectedly succeeded", failedSave)
			}
			if len(configurations.published) != 0 {
				t.Fatalf("save %d left published configurations", failedSave)
			}
			if !reverseRollbackOrder(configurations.calls) {
				t.Fatalf("save %d rollback order = %#v", failedSave, configurations.calls)
			}
		})
	}
}

func (fixture *fixture) configurationExecutor(
	configurations ConfigurationWorkspace,
) Executor {
	if fake, ok := configurations.(*fakeConfigurationWorkspace); ok {
		fake.linkWorkspace = fixture.workspace
	}
	return NewWithConfiguration(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
	)
}

func assertConfigurationCallOrder(t *testing.T, got, want []string) {
	t.Helper()
	var filtered []string
	for _, call := range got {
		if !strings.HasPrefix(call, "rollback:") {
			filtered = append(filtered, call)
		}
	}
	if !reflect.DeepEqual(filtered, want) {
		t.Fatalf("configuration calls = %#v, want %#v", filtered, want)
	}
}

func journalContainsConfigurationBytes(
	journal Journal,
	payloads map[domain.Location][]byte,
) bool {
	encoded, err := encodeJournal(journal)
	if err != nil {
		return true
	}
	for _, payload := range payloads {
		if len(payload) > 0 && strings.Contains(string(encoded), string(payload)) {
			return true
		}
	}
	return false
}

func reverseRollbackOrder(calls []string) bool {
	var rolledBack []string
	for _, call := range calls {
		if strings.HasPrefix(call, "rollback:") {
			rolledBack = append(rolledBack, call)
		}
	}
	return len(rolledBack) < 2 ||
		rolledBack[0] == "rollback:opencode.json.mainframe-permissions.json"
}

func containsConfigurationCall(calls []string, want string) bool {
	for _, call := range calls {
		if call == want {
			return true
		}
	}
	return false
}

var errConfigurationFailure = errors.New("configuration failure")

func preparedExecutorPreview(
	t *testing.T,
	desired string,
	operations ...domain.Operation,
) Preview {
	t.Helper()
	prepared := prepareOwnedConfiguration(t, desired)
	preview := testPreview(
		"release",
		"digest",
		[]domain.ComponentID{"credential-tools"},
		operations...,
	)
	preview.Configuration = prepared
	return preview
}

func configurationTransitions(plan configuration.PreparedPlan) []configuration.Transition {
	return plan.Transitions()
}
