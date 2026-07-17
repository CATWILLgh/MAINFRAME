package executor

import (
	"crypto/sha256"
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type preparedConfigurationHost struct{}

func (preparedConfigurationHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	return hostfs.Entry{}, fs.ErrNotExist
}

func prepareOwnedConfiguration(
	t testingT,
	desired string,
) configuration.PreparedPlan {
	target := testConfigurationLocation("opencode.json")
	registry := testConfigurationLocation(
		"opencode.json.mainframe-permissions.json",
	)
	resource := releasecontract.Resource{
		ID:          "opencode.permissions",
		ComponentID: domain.ComponentOpenCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Target:      target,
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportSupported,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer:            "/permission",
			DesiredMap:            desired,
			RegistryTarget:        registry,
			RegistrySchemaVersion: 1,
			EntriesPointer:        "/actions",
			EntrySchema:           "decision-rule-v1",
		},
	}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedConfigurationHost{},
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentOpenCode},
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	return prepared
}

type testingT interface {
	Helper()
	Fatalf(string, ...any)
}

type fakeConfigurationWorkspace struct {
	store                  *fakeStore
	calls                  []string
	payloads               map[domain.Location][]byte
	public                 map[domain.Location]ConfigurationState
	staged                 map[domain.Location]ConfigurationState
	published              map[domain.Location]bool
	private                map[domain.Location]FileIdentity
	nextInode              uint64
	firstPublishLinkWrites int
	linkWorkspace          *fakeWorkspace
	failCall               string
	failAfterWrite         bool
	firstCallSave          map[string]int
}

func newFakeConfigurationWorkspace(
	store *fakeStore,
) *fakeConfigurationWorkspace {
	return &fakeConfigurationWorkspace{
		store:         store,
		payloads:      make(map[domain.Location][]byte),
		public:        make(map[domain.Location]ConfigurationState),
		staged:        make(map[domain.Location]ConfigurationState),
		published:     make(map[domain.Location]bool),
		private:       make(map[domain.Location]FileIdentity),
		nextInode:     1000,
		firstCallSave: make(map[string]int),
	}
}

func (workspace *fakeConfigurationWorkspace) InspectConfiguration(
	target domain.Location,
) (ConfigurationState, error) {
	workspace.record("inspect", target)
	if workspace.fail("inspect", false) {
		return ConfigurationState{}, errConfigurationFailure
	}
	state := workspace.public[target]
	if state.Parent == (FileIdentity{}) {
		state.Parent = FileIdentity{Device: 1, Inode: 1}
	}
	return state, nil
}

func (workspace *fakeConfigurationWorkspace) PrepareConfigurationPrivate(
	mutation JournalConfigurationMutation,
) (FileIdentity, error) {
	workspace.record("private", mutation.Target)
	if workspace.fail("private", false) {
		return FileIdentity{}, errConfigurationFailure
	}
	if identity := workspace.private[mutation.Target]; identity != (FileIdentity{}) {
		return identity, nil
	}
	identity := workspace.identity()
	workspace.private[mutation.Target] = identity
	return identity, nil
}

func (workspace *fakeConfigurationWorkspace) CheckConfigurationCapabilities(
	mutation JournalConfigurationMutation,
) error {
	workspace.record("capability", mutation.Target)
	if workspace.fail("capability", false) {
		return errConfigurationFailure
	}
	return nil
}

func (workspace *fakeConfigurationWorkspace) StageConfiguration(
	mutation JournalConfigurationMutation,
	payload []byte,
) (FileIdentity, error) {
	workspace.record("stage", mutation.Target)
	workspace.payloads[mutation.Target] = append([]byte(nil), payload...)
	identity := workspace.identity()
	workspace.staged[mutation.Target] = configurationState(
		mutation.After.SHA256,
		mutation.After.Mode,
		mutation.Parent,
		identity,
	)
	if workspace.fail("stage", true) {
		return FileIdentity{}, errConfigurationFailure
	}
	return identity, nil
}

func (workspace *fakeConfigurationWorkspace) PublishConfiguration(
	mutation JournalConfigurationMutation,
) (ConfigurationState, error) {
	workspace.record("publish", mutation.Target)
	if workspace.firstPublishLinkWrites == 0 && workspace.linkWorkspace != nil {
		workspace.firstPublishLinkWrites = workspace.linkWorkspace.writeCount()
	}
	if workspace.fail("publish", false) {
		return workspace.public[mutation.Target], errConfigurationFailure
	}
	state := workspace.staged[mutation.Target]
	workspace.public[mutation.Target] = state
	workspace.published[mutation.Target] = true
	if workspace.fail("publish", true) {
		return state, errConfigurationFailure
	}
	return state, nil
}

func (workspace *fakeConfigurationWorkspace) RollbackConfiguration(
	mutation JournalConfigurationMutation,
) error {
	workspace.record("rollback", mutation.Target)
	delete(workspace.published, mutation.Target)
	delete(workspace.public, mutation.Target)
	return nil
}

func (workspace *fakeConfigurationWorkspace) FinalizeConfiguration(
	mutation JournalConfigurationMutation,
) error {
	workspace.record("finalize", mutation.Target)
	delete(workspace.staged, mutation.Target)
	return nil
}

func (workspace *fakeConfigurationWorkspace) FinalizeConfigurationPrivate(
	mutation JournalConfigurationMutation,
) error {
	workspace.record("finalize-private", mutation.Target)
	delete(workspace.private, mutation.Target)
	return nil
}

func (workspace *fakeConfigurationWorkspace) AdoptStagedConfiguration(
	mutation JournalConfigurationMutation,
) (FileIdentity, bool, error) {
	workspace.record("adopt", mutation.Target)
	if workspace.private[mutation.Target] == (FileIdentity{}) {
		return FileIdentity{}, false, errConfigurationFailure
	}
	state, exists := workspace.staged[mutation.Target]
	return state.Entry, exists, nil
}

func (workspace *fakeConfigurationWorkspace) record(
	kind string,
	target domain.Location,
) {
	workspace.calls = append(
		workspace.calls,
		fmt.Sprintf("%s:%s", kind, target.Path),
	)
	if workspace.firstCallSave[kind] == 0 {
		workspace.firstCallSave[kind] = workspace.store.saveCalls
	}
}

func (workspace *fakeConfigurationWorkspace) fail(
	kind string,
	afterWrite bool,
) bool {
	return workspace.failCall == kind && workspace.failAfterWrite == afterWrite
}

func (workspace *fakeConfigurationWorkspace) identity() FileIdentity {
	workspace.nextInode++
	return FileIdentity{Device: 1, Inode: workspace.nextInode}
}

func configurationState(
	digest string,
	mode uint32,
	parent FileIdentity,
	entry FileIdentity,
) ConfigurationState {
	return ConfigurationState{
		Exists: true, SHA256: digest, Mode: mode,
		Parent: parent, Entry: entry,
	}
}

func testConfigurationLocation(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootOpenCodeConfig, Path: path}
}

func payloadDigest(payload []byte) string {
	return fmt.Sprintf("%x", sha256.Sum256(payload))
}
