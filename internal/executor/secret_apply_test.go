package executor

import (
	"errors"
	"io/fs"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestApplyResolvesSecretsOnlyAfterFreshPreviewEquality(t *testing.T) {
	preview := secretExecutorPreview(t)
	changed := preview
	changed.Release.IndexSHA256 = testDigest("changed")
	fixture := newFixture(changed)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	resolver := &countingSecretResolver{value: "FAKE_VALUE"}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err == nil || resolver.calls != 0 {
		t.Fatalf("Apply() error = %v, resolver calls = %d", err, resolver.calls)
	}
}

func TestApplyFailsClosedWithoutSecretResolver(t *testing.T) {
	preview := secretExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)

	_, err := fixture.configurationExecutor(configurations).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "resolver") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.store.saveCalls != 0 || len(configurations.calls) != 0 {
		t.Fatal("missing resolver caused configuration work")
	}
}

func TestApplyJournalNeverContainsResolvedSecret(t *testing.T) {
	preview := secretExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	distinctive := "FAKE_SECRET_JOURNAL_SENTINEL"
	resolver := &countingSecretResolver{value: distinctive}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	for _, journal := range fixture.store.saves {
		encoded, encodeErr := encodeJournal(journal)
		if encodeErr != nil {
			t.Fatalf("encodeJournal() error = %v", encodeErr)
		}
		if strings.Contains(string(encoded), distinctive) {
			t.Fatal("transaction journal contains resolved secret")
		}
	}
	if resolver.calls != 1 {
		t.Fatalf("resolver calls = %d, want 1", resolver.calls)
	}
}

func TestApplyPrivateSecretFileJournalNeverContainsResolvedSecret(t *testing.T) {
	preview := secretFileExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	distinctive := "FAKE_PRIVATE_FILE_SECRET_SENTINEL"
	resolver := &countingSecretResolver{value: distinctive}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	for _, journal := range fixture.store.saves {
		encoded, encodeErr := encodeJournal(journal)
		if encodeErr != nil {
			t.Fatal(encodeErr)
		}
		if strings.Contains(string(encoded), distinctive) {
			t.Fatal("transaction journal contains private file secret")
		}
	}
	if resolver.calls != 1 {
		t.Fatalf("resolver calls = %d, want 1", resolver.calls)
	}
}

func TestApplyRollsBackUncertainPrivateSecretFilePublication(t *testing.T) {
	preview := secretFileExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	configurations.failCall = "publish"
	configurations.failAfterWrite = true
	resolver := &countingSecretResolver{value: "FAKE_VALUE"}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err == nil || len(configurations.published) != 0 ||
		len(configurations.public) != 0 ||
		!containsConfigurationCall(
			configurations.calls,
			"rollback:mainframe/secrets/context7-api-key",
		) {
		t.Fatalf(
			"uncertain private-file publication was not rolled back: error=%v calls=%#v",
			err,
			configurations.calls,
		)
	}
}

func TestApplyRejectsConcurrentPrivateSecretFileCreation(t *testing.T) {
	preview := secretFileExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	target := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "mainframe/secrets/context7-api-key",
	}
	configurations.public[target] = configurationState(
		testDigest("concurrent"),
		0o600,
		testIdentity(1, 20),
		testIdentity(1, 30),
	)
	resolver := &countingSecretResolver{value: "FAKE_VALUE"}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "changed after preview") ||
		len(configurations.published) != 0 {
		t.Fatalf("concurrent private-file creation error = %v", err)
	}
}

func TestApplyCollapsesVerifiedMaterializedConfigurationNoOp(t *testing.T) {
	preview := secretExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	resolver := &countingSecretResolver{value: "FAKE_VALUE"}
	setDesiredConfigurationStates(t, configurations, preview.Configuration, resolver)
	resolver.calls = 0

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if resolver.calls != 1 || fixture.store.saveCalls != 0 ||
		len(configurations.payloads) != 0 {
		t.Fatalf(
			"resolver calls = %d, saves = %d, payloads = %d",
			resolver.calls,
			fixture.store.saveCalls,
			len(configurations.payloads),
		)
	}
}

func TestApplyDoesNotCollapseChangedMaterializedState(t *testing.T) {
	preview := secretExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	resolver := &countingSecretResolver{value: "FAKE_VALUE"}
	setDesiredConfigurationStates(t, configurations, preview.Configuration, resolver)
	resolver.calls = 0
	concurrent := configurations.public[secretRegistryTarget()]
	concurrent.SHA256 = testDigest("concurrent")
	configurations.public[secretRegistryTarget()] = concurrent

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err == nil || !strings.Contains(err.Error(), "changed after preview") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.store.saveCalls == 0 {
		t.Fatal("changed materialized state was silently collapsed")
	}
}

func TestMaterializedNoOpCheckRetainsMissingConfigurationRoot(t *testing.T) {
	preview := secretExecutorPreview(t)
	materialized, err := preview.Configuration.MaterializeSecrets(
		&countingSecretResolver{value: "FAKE_VALUE"},
	)
	if err != nil {
		t.Fatal(err)
	}
	base := newFakeConfigurationWorkspace(nil)
	executor := Executor{
		configurations: missingConfigurationWorkspace{base},
	}

	collapsed, err := executor.collapseConfigurationNoOps(materialized)

	if err != nil {
		t.Fatalf("collapseConfigurationNoOps() error = %v", err)
	}
	if len(collapsed.Transitions()) != len(materialized.Transitions()) {
		t.Fatal("missing configuration root was treated as an error or no-op")
	}
}

type missingConfigurationWorkspace struct {
	*fakeConfigurationWorkspace
}

func (missingConfigurationWorkspace) InspectConfiguration(
	domain.Location,
) (ConfigurationState, error) {
	return ConfigurationState{}, fs.ErrNotExist
}

func TestApplyRedactsSecretResolverFailure(t *testing.T) {
	preview := secretExecutorPreview(t)
	fixture := newFixture(preview)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	distinctive := "FAKE_SECRET_RESOLVER_ERROR_SENTINEL"
	resolver := &countingSecretResolver{err: errors.New(distinctive)}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Apply(preview)

	if err == nil || strings.Contains(err.Error(), distinctive) {
		t.Fatalf("Apply() error = %v", err)
	}
}

func TestRecoverDoesNotResolveSecrets(t *testing.T) {
	step := installJournalStep("one", StepPrepared)
	fixture := newFixture(Preview{})
	fixture.store.journal = journalWith(TransactionInProgress, step)
	configurations := newFakeConfigurationWorkspace(fixture.store)
	resolver := &countingSecretResolver{
		err: errors.New("resolver must not run during recovery"),
	}

	_, err := NewWithConfigurationAndSecrets(
		fixture.locker,
		fixture.store,
		fixture.refresher,
		fixture.workspace,
		configurations,
		resolver,
	).Recover()

	if err != nil {
		t.Fatalf("Recover() error = %v", err)
	}
	if resolver.calls != 0 {
		t.Fatalf("resolver calls = %d, want 0", resolver.calls)
	}
}
