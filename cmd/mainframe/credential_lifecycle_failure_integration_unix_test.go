//go:build darwin || linux

package main

import (
	"bytes"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
)

var errInjectedCredentialPublication = errors.New("injected credential publication failure")
var errInjectedCredentialStage = errors.New("injected credential staging failure")
var errInjectedCredentialCommitSave = errors.New("injected credential commit save failure")

type credentialFileSnapshot struct {
	payload  []byte
	mode     fs.FileMode
	digest   string
	identity executor.FileIdentity
}

type uncertainCredentialWorkspace struct {
	executor.ConfigurationWorkspace
}

type uncertainCredentialStageWorkspace struct {
	executor.ConfigurationWorkspace
}

func (workspace uncertainCredentialStageWorkspace) StageConfiguration(
	mutation executor.JournalConfigurationMutation,
	payload []byte,
) (executor.FileIdentity, error) {
	identity, err := workspace.ConfigurationWorkspace.StageConfiguration(mutation, payload)
	if err != nil {
		return identity, err
	}
	return identity, errInjectedCredentialStage
}

func (workspace uncertainCredentialWorkspace) PublishConfiguration(
	mutation executor.JournalConfigurationMutation,
) (executor.ConfigurationState, error) {
	state, err := workspace.ConfigurationWorkspace.PublishConfiguration(mutation)
	if err != nil {
		return state, err
	}
	return state, errInjectedCredentialPublication
}

type failingCredentialCommitStore struct {
	applyStateStore
}

func (store failingCredentialCommitStore) Save(journal executor.Journal) error {
	if journal.Status == executor.TransactionCommitted {
		return errInjectedCredentialCommitSave
	}
	return store.applyStateStore.Save(journal)
}

func TestCredentialPublicationFailureRestoresExactPreviousDocument(t *testing.T) {
	fixture := newCredentialLifecycleFixtureWithDecorators(
		t,
		func(workspace executor.ConfigurationWorkspace) executor.ConfigurationWorkspace {
			return uncertainCredentialWorkspace{ConfigurationWorkspace: workspace}
		},
		nil,
	)
	previous := seedCredentialLifecycleDocument(t, fixture, "Previous", "CONTEXT7_PREVIOUS_KEY")
	desired := credentialLifecycleInstances(t, fixture.definitions, "Desired", "CONTEXT7_DESIRED_KEY")
	reviewed := reviewCredentialLifecycleChange(t, fixture, desired)

	_, err := fixture.service.ApplyCredentials(reviewed)
	if !errors.Is(err, errInjectedCredentialPublication) {
		t.Fatalf("ApplyCredentials() error = %v", err)
	}

	assertCredentialSnapshot(t, fixture, previous)
	assertCredentialDirectoryState(t, fixture.instancesPath, true)
	assertCredentialJournalAbsent(t, fixture.stateRoot)
	recovered, err := fixture.service.Recover()
	if err != nil || recovered.Recovered {
		t.Fatalf("Recover() = %#v, %v", recovered, err)
	}
}

func TestCredentialStagingFailureLeavesNoPartialMetadata(t *testing.T) {
	fixture := newCredentialLifecycleFixtureWithDecorators(
		t,
		func(workspace executor.ConfigurationWorkspace) executor.ConfigurationWorkspace {
			return uncertainCredentialStageWorkspace{ConfigurationWorkspace: workspace}
		},
		nil,
	)
	previous := seedCredentialLifecycleDocument(t, fixture, "Previous", "CONTEXT7_PREVIOUS_KEY")
	desired := credentialLifecycleInstances(t, fixture.definitions, "Desired", "CONTEXT7_DESIRED_KEY")
	reviewed := reviewCredentialLifecycleChange(t, fixture, desired)

	_, err := fixture.service.ApplyCredentials(reviewed)
	if !errors.Is(err, errInjectedCredentialStage) {
		t.Fatalf("ApplyCredentials() error = %v", err)
	}

	assertCredentialSnapshot(t, fixture, previous)
	assertCredentialDirectoryState(t, fixture.instancesPath, true)
	assertCredentialJournalAbsent(t, fixture.stateRoot)
}

func TestCredentialCreatePublicationFailureRestoresAbsence(t *testing.T) {
	fixture := newCredentialLifecycleFixtureWithDecorators(
		t,
		func(workspace executor.ConfigurationWorkspace) executor.ConfigurationWorkspace {
			return uncertainCredentialWorkspace{ConfigurationWorkspace: workspace}
		},
		nil,
	)
	desired := credentialLifecycleInstances(t, fixture.definitions, "Desired", "CONTEXT7_DESIRED_KEY")
	reviewed := reviewCredentialLifecycleChange(t, fixture, desired)

	_, err := fixture.service.ApplyCredentials(reviewed)
	if !errors.Is(err, errInjectedCredentialPublication) {
		t.Fatalf("ApplyCredentials() error = %v", err)
	}
	if _, statErr := os.Lstat(fixture.instancesPath); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("credential target after failed create = %v", statErr)
	}
	assertCredentialDirectoryState(t, fixture.instancesPath, false)
	assertCredentialJournalAbsent(t, fixture.stateRoot)
}

func TestCredentialCommitSaveFailureRecoversExactPreviousDocument(t *testing.T) {
	fixture := newCredentialLifecycleFixtureWithDecorators(
		t,
		nil,
		func(store applyStateStore) applyStateStore {
			return failingCredentialCommitStore{applyStateStore: store}
		},
	)
	previous := seedCredentialLifecycleDocument(t, fixture, "Previous", "CONTEXT7_PREVIOUS_KEY")
	desired := credentialLifecycleInstances(t, fixture.definitions, "Desired", "CONTEXT7_DESIRED_KEY")
	desiredPayload := encodeCredentialLifecycleInstances(t, desired)
	reviewed := reviewCredentialLifecycleChange(t, fixture, desired)

	_, err := fixture.service.ApplyCredentials(reviewed)
	if !errors.Is(err, errInjectedCredentialCommitSave) {
		t.Fatalf("ApplyCredentials() error = %v", err)
	}
	published := assertPublishedCredentialDocument(t, fixture, previous, desiredPayload)
	assertPublishedCredentialJournal(t, fixture.stateRoot, published)

	recovered, err := fixture.service.Recover()
	if err != nil || !recovered.Recovered {
		t.Fatalf("Recover() = %#v, %v", recovered, err)
	}
	assertCredentialSnapshot(t, fixture, previous)
	assertCredentialDirectoryState(t, fixture.instancesPath, true)
	assertCredentialJournalAbsent(t, fixture.stateRoot)
}

func seedCredentialLifecycleDocument(
	t *testing.T,
	fixture credentialLifecycleFixture,
	name string,
	reference string,
) credentialFileSnapshot {
	t.Helper()
	instances := credentialLifecycleInstances(t, fixture.definitions, name, reference)
	payload := encodeCredentialLifecycleInstances(t, instances)
	parent := filepath.Dir(fixture.instancesPath)
	if err := os.MkdirAll(parent, 0o700); err != nil {
		t.Fatalf("create credential parent: %v", err)
	}
	if err := os.Chmod(parent, 0o700); err != nil {
		t.Fatalf("secure credential parent: %v", err)
	}
	if err := os.WriteFile(fixture.instancesPath, payload, 0o600); err != nil {
		t.Fatalf("write previous credentials: %v", err)
	}
	return snapshotCredentialLifecycleFile(t, fixture)
}

func encodeCredentialLifecycleInstances(
	t *testing.T,
	instances credentialcatalog.Instances,
) []byte {
	t.Helper()
	payload, err := credentialcatalog.EncodeInstances(instances)
	if err != nil {
		t.Fatalf("EncodeInstances() error = %v", err)
	}
	return payload
}

func reviewCredentialLifecycleChange(
	t *testing.T,
	fixture credentialLifecycleFixture,
	desired credentialcatalog.Instances,
) application.ReviewedPlan {
	t.Helper()
	reviewed, err := fixture.service.Review(application.Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	return reviewed
}

func snapshotCredentialLifecycleFile(
	t *testing.T,
	fixture credentialLifecycleFixture,
) credentialFileSnapshot {
	t.Helper()
	payload, err := os.ReadFile(fixture.instancesPath)
	if err != nil {
		t.Fatalf("read credential document: %v", err)
	}
	info, err := os.Stat(fixture.instancesPath)
	if err != nil {
		t.Fatalf("stat credential document: %v", err)
	}
	workspace, err := linkworkspace.New(fixture.layout.Source(), fixture.layout.Targets())
	if err != nil {
		t.Fatalf("open credential workspace: %v", err)
	}
	state, err := workspace.InspectConfiguration(domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: credentialcatalog.UserInstancesPath,
	})
	if err != nil {
		t.Fatalf("inspect credential document: %v", err)
	}
	return credentialFileSnapshot{
		payload: payload, mode: info.Mode().Perm(),
		digest: state.SHA256, identity: state.Entry,
	}
}

func assertCredentialSnapshot(
	t *testing.T,
	fixture credentialLifecycleFixture,
	want credentialFileSnapshot,
) {
	t.Helper()
	got := snapshotCredentialLifecycleFile(t, fixture)
	if !bytes.Equal(got.payload, want.payload) ||
		got.mode != want.mode || got.identity != want.identity {
		t.Fatalf("credential snapshot changed: got=%#v want=%#v", got, want)
	}
	parsed, err := credentialcatalog.ParseInstances(got.payload, fixture.definitions)
	if err != nil || reflect.DeepEqual(parsed, credentialcatalog.Instances{}) {
		t.Fatalf("restored credential document is invalid: %#v, %v", parsed, err)
	}
}

func assertPublishedCredentialDocument(
	t *testing.T,
	fixture credentialLifecycleFixture,
	previous credentialFileSnapshot,
	wantPayload []byte,
) credentialFileSnapshot {
	t.Helper()
	got := snapshotCredentialLifecycleFile(t, fixture)
	if !bytes.Equal(got.payload, wantPayload) || got.mode != 0o600 {
		t.Fatalf("published credential document = %#v", got)
	}
	if got.identity == previous.identity {
		t.Fatal("publication retained the previous file identity")
	}
	return got
}

func assertPublishedCredentialJournal(
	t *testing.T,
	stateRoot string,
	published credentialFileSnapshot,
) {
	t.Helper()
	journal, err := executor.ReadUnixJournal(stateRoot)
	if err != nil || journal == nil {
		t.Fatalf("ReadUnixJournal() = %#v, %v", journal, err)
	}
	if journal.Status != executor.TransactionInProgress ||
		len(journal.Configurations) != 1 ||
		len(journal.Configurations[0].Mutations) != 1 ||
		journal.Configurations[0].Mutations[0].Phase != executor.StepPublished {
		t.Fatalf("published journal = %#v", journal)
	}
	after := journal.Configurations[0].Mutations[0].After
	if after.SHA256 != published.digest || after.Mode != uint32(published.mode) ||
		after.Entry != published.identity {
		t.Fatalf("journal after-image = %#v, published = %#v", after, published)
	}
}

func assertCredentialJournalAbsent(t *testing.T, stateRoot string) {
	t.Helper()
	journal, err := executor.ReadUnixJournal(stateRoot)
	if err != nil || journal != nil {
		t.Fatalf("ReadUnixJournal() = %#v, %v", journal, err)
	}
}

func assertCredentialDirectoryState(t *testing.T, target string, wantDocument bool) {
	t.Helper()
	entries, err := os.ReadDir(filepath.Dir(target))
	if errors.Is(err, os.ErrNotExist) && !wantDocument {
		return
	}
	if err != nil {
		t.Fatalf("read credential directory: %v", err)
	}
	if wantDocument && len(entries) == 1 && entries[0].Name() == filepath.Base(target) {
		return
	}
	if !wantDocument && len(entries) == 0 {
		return
	}
	t.Fatalf("credential directory residue = %#v", entries)
}
