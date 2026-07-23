//go:build darwin || linux

package linkworkspace

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

type configurationTestFixture struct {
	workspace Workspace
	location  domain.Location
	target    string
}

func newConfigurationFixture(
	t *testing.T,
	name string,
	content []byte,
	mode os.FileMode,
) configurationTestFixture {
	t.Helper()
	base := newWorkspaceFixture(t)
	fixture := configurationTestFixture{
		workspace: base.workspace,
		location:  base.location(domain.ArtifactPath(name)),
		target:    base.target,
	}
	if content != nil {
		if err := os.WriteFile(fixture.publicPath(), content, mode); err != nil {
			t.Fatalf("write configuration: %v", err)
		}
	}
	return fixture
}

func (fixture configurationTestFixture) publicPath() string {
	return filepath.Join(fixture.target, string(fixture.location.Path))
}

func (fixture configurationTestFixture) inspect(t *testing.T) executor.ConfigurationState {
	t.Helper()
	state, err := fixture.workspace.InspectConfiguration(fixture.location)
	if err != nil {
		t.Fatalf("InspectConfiguration() error = %v", err)
	}
	return state
}

func (fixture configurationTestFixture) preparedMutation(
	t *testing.T,
	after []byte,
	mode uint32,
) executor.JournalConfigurationMutation {
	t.Helper()
	before := fixture.inspect(t)
	name, err := fixture.workspace.AllocatePrivateName()
	if err != nil {
		t.Fatalf("AllocatePrivateName() error = %v", err)
	}
	return executor.JournalConfigurationMutation{
		Disposition: executor.ConfigurationPresent,
		Target:      fixture.location,
		Before:      configurationImage(before),
		After: executor.ConfigurationFileImage{
			Exists: true,
			SHA256: digestBytes(after),
			Mode:   mode,
		},
		Parent:     before.Parent,
		Private:    executor.PrivateDirectory{Name: name},
		StagedName: "staged",
		Phase:      executor.StepPrepared,
	}
}

func (fixture configurationTestFixture) preparedRemovalMutation(
	t *testing.T,
) executor.JournalConfigurationMutation {
	t.Helper()
	mutation := fixture.preparedMutation(t, nil, 0)
	mutation.Disposition = executor.ConfigurationRemoveExactDocument
	mutation.After = executor.ConfigurationFileImage{}
	return mutation
}

func (fixture configurationTestFixture) prepareAndStage(
	t *testing.T,
	mutation *executor.JournalConfigurationMutation,
	payload []byte,
) {
	t.Helper()
	identity, err := fixture.workspace.PrepareConfigurationPrivate(*mutation)
	if err != nil {
		t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
	}
	mutation.Private.Identity = identity
	if err := fixture.workspace.CheckConfigurationCapabilities(*mutation); err != nil {
		t.Fatalf("CheckConfigurationCapabilities() error = %v", err)
	}
	staged, err := fixture.workspace.StageConfiguration(*mutation, payload)
	if err != nil {
		t.Fatalf("StageConfiguration() error = %v", err)
	}
	mutation.StagedIdentity = staged
	mutation.Phase = executor.StepStaged
}

func (fixture configurationTestFixture) prepareRemoval(
	t *testing.T,
	mutation *executor.JournalConfigurationMutation,
) {
	t.Helper()
	identity, err := fixture.workspace.PrepareConfigurationPrivate(*mutation)
	if err != nil {
		t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
	}
	mutation.Private.Identity = identity
	if err := fixture.workspace.CheckConfigurationCapabilities(*mutation); err != nil {
		t.Fatalf("CheckConfigurationCapabilities() error = %v", err)
	}
	mutation.Phase = executor.StepPrivateCreated
}

func (fixture configurationTestFixture) finalize(
	t *testing.T,
	mutation executor.JournalConfigurationMutation,
) {
	t.Helper()
	if err := fixture.workspace.FinalizeConfiguration(mutation); err != nil {
		t.Fatalf("FinalizeConfiguration() error = %v", err)
	}
	fixture.finalizePrivate(t, mutation)
}

func (fixture configurationTestFixture) finalizePrivate(
	t *testing.T,
	mutation executor.JournalConfigurationMutation,
) {
	t.Helper()
	if err := fixture.workspace.FinalizeConfigurationPrivate(mutation); err != nil {
		t.Fatalf("FinalizeConfigurationPrivate() error = %v", err)
	}
	if err := fixture.workspace.FinalizeConfigurationPrivate(mutation); err != nil {
		t.Fatalf("idempotent FinalizeConfigurationPrivate() error = %v", err)
	}
	if _, err := os.Lstat(filepath.Join(fixture.target, mutation.Private.Name)); !os.IsNotExist(err) {
		t.Fatalf("private directory remains: %v", err)
	}
}

func configurationImage(state executor.ConfigurationState) executor.ConfigurationFileImage {
	return executor.ConfigurationFileImage{
		Exists: state.Exists,
		SHA256: state.SHA256,
		Mode:   state.Mode,
		Entry:  state.Entry,
	}
}

func assertConfigurationState(
	t *testing.T,
	state executor.ConfigurationState,
	content []byte,
	mode uint32,
) {
	t.Helper()
	if !state.Exists || state.SHA256 != digestBytes(content) || state.Mode != mode ||
		state.Parent == (executor.FileIdentity{}) ||
		state.Entry == (executor.FileIdentity{}) {
		t.Fatalf("configuration state = %#v", state)
	}
}

func digestBytes(content []byte) string {
	sum := sha256.Sum256(content)
	return hex.EncodeToString(sum[:])
}
