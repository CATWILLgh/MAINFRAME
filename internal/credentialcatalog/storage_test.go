package credentialcatalog

import (
	"errors"
	"io/fs"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestObserveInstancesRejectsUnsafeAndInvalidDocuments(t *testing.T) {
	definitions := testDefinitions(t)
	valid := distinctInstancesPayload()
	tests := map[string]struct {
		entry hostfs.Entry
		err   error
	}{
		"symlink": {
			entry: hostfs.Entry{Kind: hostfs.EntrySymlink},
		},
		"public mode": {
			entry: credentialStorageEntry(valid, 0o644),
		},
		"unknown version": {
			entry: credentialStorageEntry(
				[]byte(`{"schema_version":2,"kind":"mainframe-credential-instances","instances":[]}`),
				0o600,
			),
		},
		"malformed": {
			entry: credentialStorageEntry([]byte(`{"schema_version":`), 0o600),
		},
		"inspection error": {
			err: errors.New("inspection failed"),
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			host := credentialStorageHost{entry: test.entry, err: test.err}
			if _, err := ObserveInstances(host, definitions); err == nil {
				t.Fatal("ObserveInstances() accepted unsafe state")
			}
		})
	}
}

func TestPrepareInstancesCreatesPrivateAtomicMutation(t *testing.T) {
	definitions := testDefinitions(t)
	snapshot, err := ObserveInstances(
		credentialStorageHost{err: fs.ErrNotExist},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	desired, err := BuildInstances([]Instance{{
		ID: "dokploy-home", ServiceID: "dokploy",
		Name: "Home", Purpose: "Personal documentation lookup",
		Credentials: []CredentialBinding{{
			RoleID: "api-key",
			Secret: SecretReference{
				Backend: BackendSecretEnvironment,
				Name:    "DOKPLOY_HOME_KEY",
			},
		}},
	}}, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}

	plan, err := snapshot.Prepare(desired)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	transitions := plan.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 1 {
		t.Fatalf("transitions = %#v", transitions)
	}
	mutation := transitions[0].Mutations[0]
	if mutation.Target != (domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: UserInstancesPath,
	}) || mutation.Before.Exists || mutation.After.Mode != 0o600 {
		t.Fatalf("mutation = %#v", mutation)
	}
	if _, err := ParseInstances(mutation.After.Content, definitions); err != nil {
		t.Fatalf("prepared document is invalid: %v", err)
	}
}

func TestPrepareInstancesUsesExactBeforeImageAndSkipsNoop(t *testing.T) {
	definitions := testDefinitions(t)
	payload := distinctInstancesPayload()
	entry := credentialStorageEntry(payload, 0o600)
	snapshot, err := ObserveInstances(
		credentialStorageHost{entry: entry},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}

	noop, err := snapshot.Prepare(snapshot.Instances())
	if err != nil {
		t.Fatalf("Prepare(noop) error = %v", err)
	}
	if len(noop.Transitions()) != 0 {
		t.Fatalf("noop transitions = %#v", noop.Transitions())
	}

	current := snapshot.Instances()
	replacement := current.ForService("dokploy")[0]
	replacement.Name = "Home production"
	updated, _, err := EditInstance(
		current,
		replacement.ID,
		replacement,
		definitions,
	)
	if err != nil {
		t.Fatalf("EditInstance() error = %v", err)
	}
	plan, err := snapshot.Prepare(updated)
	if err != nil {
		t.Fatalf("Prepare(update) error = %v", err)
	}
	before := plan.Transitions()[0].Mutations[0].Before
	if !before.Exists || before.Mode != 0o600 ||
		before.Device != entry.Device || before.Inode != entry.Inode ||
		before.SHA256 == "" {
		t.Fatalf("before image = %#v", before)
	}
}

type credentialStorageHost struct {
	entry hostfs.Entry
	err   error
}

func (host credentialStorageHost) Inspect(
	location domain.Location,
	includeContent bool,
) (hostfs.Entry, error) {
	if location != (domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: UserInstancesPath,
	}) || !includeContent {
		return hostfs.Entry{}, errors.New("unexpected inspection")
	}
	return host.entry, host.err
}

func credentialStorageEntry(payload []byte, mode uint32) hostfs.Entry {
	return hostfs.Entry{
		Kind: hostfs.EntryRegular, Content: payload, Mode: mode,
		Device: 11, Inode: 22, BirthSeconds: 33, BirthNanoseconds: 44,
	}
}
