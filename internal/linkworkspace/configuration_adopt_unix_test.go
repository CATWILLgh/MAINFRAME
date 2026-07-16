//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestAdoptStagedConfigurationRecoversOnlyExactPrivateFile(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	fixture.prepareAndStage(t, &mutation, []byte("after"))
	stagedIdentity := mutation.StagedIdentity
	mutation.StagedIdentity = executor.FileIdentity{}
	mutation.Phase = executor.StepPrivateCreated

	adopted, exists, err := fixture.workspace.AdoptStagedConfiguration(mutation)
	if err != nil || !exists || adopted != stagedIdentity {
		t.Fatalf("adopted = %#v, %t, %v", adopted, exists, err)
	}

	stagedPath := filepath.Join(
		fixture.target,
		mutation.Private.Name,
		mutation.StagedName,
	)
	if err := os.Chmod(stagedPath, 0o400); err != nil {
		t.Fatal(err)
	}
	if _, _, err := fixture.workspace.AdoptStagedConfiguration(mutation); err == nil {
		t.Fatal("AdoptStagedConfiguration() accepted a mismatched file")
	}
	if _, err := os.Lstat(stagedPath); err != nil {
		t.Fatalf("mismatched staged file was deleted: %v", err)
	}
}

func TestAdoptStagedConfigurationRemovesInterruptedWritingFile(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o400)
	identity, err := fixture.workspace.PrepareConfigurationPrivate(mutation)
	if err != nil {
		t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
	}
	mutation.Private.Identity = identity
	writing := filepath.Join(
		fixture.target,
		mutation.Private.Name,
		configurationWritingName,
	)
	if err := os.WriteFile(writing, []byte("part"), 0o600); err != nil {
		t.Fatalf("write interrupted stage: %v", err)
	}

	adopted, exists, err := fixture.workspace.AdoptStagedConfiguration(mutation)

	if err != nil || exists || adopted != (executor.FileIdentity{}) {
		t.Fatalf("adopted = %#v, %t, %v", adopted, exists, err)
	}
	if _, err := os.Lstat(writing); !os.IsNotExist(err) {
		t.Fatalf("interrupted writing file remains: %v", err)
	}
}

func TestAdoptStagedConfigurationPreservesUnsafeWritingEntry(t *testing.T) {
	fixture := newConfigurationFixture(t, "settings.json", nil, 0)
	mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
	identity, err := fixture.workspace.PrepareConfigurationPrivate(mutation)
	if err != nil {
		t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
	}
	mutation.Private.Identity = identity
	writing := filepath.Join(
		fixture.target,
		mutation.Private.Name,
		configurationWritingName,
	)
	if err := os.Symlink("foreign", writing); err != nil {
		t.Fatalf("create unsafe writing entry: %v", err)
	}

	if _, _, err := fixture.workspace.AdoptStagedConfiguration(mutation); err == nil {
		t.Fatal("AdoptStagedConfiguration() removed an unsafe writing entry")
	}
	if _, err := os.Lstat(writing); err != nil {
		t.Fatalf("unsafe writing entry was deleted: %v", err)
	}
}
