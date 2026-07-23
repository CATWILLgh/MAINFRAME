//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestConfigurationCreatePublishesAndRollsBackAfterUnrecordedRename(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("created"), 0o400)
	fixture.prepareAndStage(t, &mutation, []byte("created"))

	published, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil {
		t.Fatalf("PublishConfiguration() error = %v", err)
	}
	assertConfigurationState(t, published, []byte("created"), 0o400)
	retried, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil || retried != published {
		t.Fatalf("retry = %#v, %v; want %#v", retried, err, published)
	}
	if err := fixture.workspace.RollbackConfiguration(mutation); err != nil {
		t.Fatalf("RollbackConfiguration() error = %v", err)
	}
	if err := fixture.workspace.RollbackConfiguration(mutation); err != nil {
		t.Fatalf("idempotent RollbackConfiguration() error = %v", err)
	}
	state := fixture.inspect(t)
	if state.Exists {
		t.Fatalf("created configuration survived rollback: %#v", state)
	}
	mutation.Phase = executor.StepRolledBack
	fixture.finalize(t, mutation)
}

func TestConfigurationReplacementExchangesAndRestoresExactInode(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	beforeIdentity := mutation.Before.Entry
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	stagedIdentity := mutation.StagedIdentity

	published, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil {
		t.Fatalf("PublishConfiguration() error = %v", err)
	}
	if published.Entry != stagedIdentity {
		t.Fatalf("published identity = %#v, want staged %#v", published.Entry, stagedIdentity)
	}
	if _, err := fixture.workspace.PublishConfiguration(mutation); err != nil {
		t.Fatalf("crash-inference retry error = %v", err)
	}
	if err := fixture.workspace.RollbackConfiguration(mutation); err != nil {
		t.Fatalf("RollbackConfiguration() error = %v", err)
	}
	restored := fixture.inspect(t)
	assertConfigurationState(t, restored, []byte("before"), 0o600)
	if restored.Entry != beforeIdentity {
		t.Fatalf("restored identity = %#v, want %#v", restored.Entry, beforeIdentity)
	}
	mutation.Phase = executor.StepRolledBack
	fixture.finalize(t, mutation)
}

func TestCommittedConfigurationFinalizationDeletesOnlyExactRetainedFile(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o400)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	published, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil {
		t.Fatalf("PublishConfiguration() error = %v", err)
	}
	mutation.After.Entry = published.Entry
	mutation.Phase = executor.StepPublished

	if err := fixture.workspace.FinalizeConfiguration(mutation); err != nil {
		t.Fatalf("FinalizeConfiguration() error = %v", err)
	}
	if err := fixture.workspace.FinalizeConfiguration(mutation); err != nil {
		t.Fatalf("idempotent FinalizeConfiguration() error = %v", err)
	}
	fixture.finalizePrivate(t, mutation)
	assertConfigurationState(t, fixture.inspect(t), []byte("after"), 0o400)
}

func TestConfigurationRemovalPublishesAndRestoresExactBefore(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
	mutation := fixture.preparedRemovalMutation(t)
	beforeIdentity := mutation.Before.Entry
	fixture.prepareRemoval(t, &mutation)

	published, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil || published.Exists || published.Entry != (executor.FileIdentity{}) {
		t.Fatalf("PublishConfiguration() = %#v, %v", published, err)
	}
	retried, err := fixture.workspace.PublishConfiguration(mutation)
	if err != nil || retried != published {
		t.Fatalf("retry = %#v, %v; want %#v", retried, err, published)
	}
	if err := fixture.workspace.RollbackConfiguration(mutation); err != nil {
		t.Fatalf("RollbackConfiguration() error = %v", err)
	}
	if err := fixture.workspace.RollbackConfiguration(mutation); err != nil {
		t.Fatalf("idempotent RollbackConfiguration() error = %v", err)
	}
	restored := fixture.inspect(t)
	assertConfigurationState(t, restored, []byte("before"), 0o600)
	if restored.Entry != beforeIdentity {
		t.Fatalf("restored identity = %#v, want %#v", restored.Entry, beforeIdentity)
	}
	mutation.Phase = executor.StepRolledBack
	fixture.finalize(t, mutation)
}

func TestCommittedConfigurationRemovalDeletesOnlyExactRetainedBefore(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
	mutation := fixture.preparedRemovalMutation(t)
	fixture.prepareRemoval(t, &mutation)
	if _, err := fixture.workspace.PublishConfiguration(mutation); err != nil {
		t.Fatalf("PublishConfiguration() error = %v", err)
	}
	mutation.Phase = executor.StepPublished

	if err := fixture.workspace.FinalizeConfiguration(mutation); err != nil {
		t.Fatalf("FinalizeConfiguration() error = %v", err)
	}
	if err := fixture.workspace.FinalizeConfiguration(mutation); err != nil {
		t.Fatalf("idempotent FinalizeConfiguration() error = %v", err)
	}
	fixture.finalizePrivate(t, mutation)
	if state := fixture.inspect(t); state.Exists {
		t.Fatalf("removed configuration remains: %#v", state)
	}
}

func TestConfigurationRemovalRejectsChangedPublicAndPrivate(t *testing.T) {
	t.Run("public", func(t *testing.T) {
		fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
		mutation := fixture.preparedRemovalMutation(t)
		fixture.prepareRemoval(t, &mutation)
		if err := os.Remove(fixture.publicPath()); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(fixture.publicPath(), []byte("foreign"), 0o600); err != nil {
			t.Fatal(err)
		}
		if _, err := fixture.workspace.PublishConfiguration(mutation); err == nil {
			t.Fatal("PublishConfiguration() removed a changed public file")
		}
	})
	t.Run("private", func(t *testing.T) {
		fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
		mutation := fixture.preparedRemovalMutation(t)
		fixture.prepareRemoval(t, &mutation)
		if _, err := fixture.workspace.PublishConfiguration(mutation); err != nil {
			t.Fatalf("PublishConfiguration() error = %v", err)
		}
		privatePath := filepath.Join(
			fixture.target,
			mutation.Private.Name,
			mutation.StagedName,
		)
		if err := os.Remove(privatePath); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(privatePath, []byte("foreign"), 0o600); err != nil {
			t.Fatal(err)
		}
		if err := fixture.workspace.RollbackConfiguration(mutation); err == nil {
			t.Fatal("RollbackConfiguration() restored a changed private file")
		}
		mutation.Phase = executor.StepPublished
		if err := fixture.workspace.FinalizeConfiguration(mutation); err == nil {
			t.Fatal("FinalizeConfiguration() deleted a changed private file")
		}
	})
}

func TestInspectConfigurationRejectsSymlinkHardlinkAndWrongType(t *testing.T) {
	tests := map[string]func(*testing.T, string){
		"symlink": func(t *testing.T, target string) {
			if err := os.Symlink("elsewhere", target); err != nil {
				t.Fatal(err)
			}
		},
		"hardlink": func(t *testing.T, target string) {
			source := filepath.Join(filepath.Dir(target), "source")
			if err := os.WriteFile(source, []byte("shared"), 0o600); err != nil {
				t.Fatal(err)
			}
			if err := os.Link(source, target); err != nil {
				t.Fatal(err)
			}
		},
		"directory": func(t *testing.T, target string) {
			if err := os.Mkdir(target, 0o700); err != nil {
				t.Fatal(err)
			}
		},
	}
	for name, create := range tests {
		t.Run(name, func(t *testing.T) {
			fixture := newConfigurationFixture(t, "settings.json", nil, 0)
			create(t, fixture.publicPath())
			if _, err := fixture.workspace.InspectConfiguration(fixture.location); err == nil {
				t.Fatal("InspectConfiguration() accepted unsafe target")
			}
		})
	}
}

func TestConfigurationPublicationRejectsChangedPublicIdentity(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", []byte("before"), 0o600)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	if err := os.Remove(fixture.publicPath()); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fixture.publicPath(), []byte("replacement"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := fixture.workspace.PublishConfiguration(mutation); err == nil {
		t.Fatal("PublishConfiguration() replaced a changed public file")
	}
	content, err := os.ReadFile(fixture.publicPath())
	if err != nil || string(content) != "replacement" {
		t.Fatalf("competing file changed: %q, %v", content, err)
	}
}

func TestConfigurationCreateNeverReplacesAppearingDestination(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	if err := os.WriteFile(fixture.publicPath(), []byte("foreign"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := fixture.workspace.PublishConfiguration(mutation); err == nil {
		t.Fatal("PublishConfiguration() replaced an appearing destination")
	}
	content, err := os.ReadFile(fixture.publicPath())
	if err != nil || string(content) != "foreign" {
		t.Fatalf("appearing destination changed: %q, %v", content, err)
	}
}

func TestStageConfigurationAdoptsOnlyExactPrivateFile(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	adopted, err := fixture.workspace.StageConfiguration(mutation, []byte("ignored"))
	if err != nil || adopted != mutation.StagedIdentity {
		t.Fatalf("adopted identity = %#v, error = %v", adopted, err)
	}

	stagedPath := filepath.Join(
		fixture.target,
		mutation.Private.Name,
		mutation.StagedName,
	)
	if err := os.Chmod(stagedPath, 0o400); err != nil {
		t.Fatal(err)
	}
	if _, err := fixture.workspace.StageConfiguration(mutation, []byte("after")); err == nil {
		t.Fatal("StageConfiguration() adopted a mode-mismatched file")
	}
	if _, err := os.Lstat(stagedPath); err != nil {
		t.Fatalf("mismatched staged file was deleted: %v", err)
	}
}

func TestFinalizeConfigurationRefusesAmbiguousPrivateDeletion(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	mutation.Phase = executor.StepRolledBack
	stagedPath := filepath.Join(
		fixture.target,
		mutation.Private.Name,
		mutation.StagedName,
	)
	if err := os.Chmod(stagedPath, 0o400); err != nil {
		t.Fatal(err)
	}
	if err := fixture.workspace.FinalizeConfiguration(mutation); err == nil {
		t.Fatal("FinalizeConfiguration() deleted a mismatched private file")
	}
	if _, err := os.Lstat(stagedPath); err != nil {
		t.Fatalf("mismatched private file was deleted: %v", err)
	}
}

func TestConfigurationPublicationRejectsChangedParentIdentity(t *testing.T) {
	base := newWorkspaceFixture(t)
	nested := filepath.Join(base.target, "nested")
	if err := os.Mkdir(nested, 0o700); err != nil {
		t.Fatal(err)
	}
	fixture := configurationTestFixture{
		workspace: base.workspace,
		location:  base.location("nested/settings.json"),
		target:    base.target,
	}
	if err := os.WriteFile(fixture.publicPath(), []byte("before"), 0o600); err != nil {
		t.Fatal(err)
	}
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	if err := os.Rename(nested, filepath.Join(base.target, "old-nested")); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(nested, 0o700); err != nil {
		t.Fatal(err)
	}
	if _, err := fixture.workspace.PublishConfiguration(mutation); err == nil {
		t.Fatal("PublishConfiguration() accepted a changed parent")
	}
}

func TestConfigurationWorkspaceImplementsExecutorContract(t *testing.T) {
	var _ executor.ConfigurationWorkspace = Workspace{}
}
