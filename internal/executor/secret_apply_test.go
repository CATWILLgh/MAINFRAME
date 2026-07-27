package executor

import (
	"errors"
	"io/fs"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
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

type countingSecretResolver struct {
	value string
	err   error
	calls int
}

func (resolver *countingSecretResolver) ResolveSecret(string) (string, error) {
	resolver.calls++
	return resolver.value, resolver.err
}

func secretExecutorPreview(t *testing.T) Preview {
	t.Helper()
	configTarget := secretConfigTarget()
	registryTarget := secretRegistryTarget()
	resourceID := "antigravity2.mcp.context7"
	transitions := []configuration.Transition{{
		ResourceIDs: []string{resourceID},
		Mutations: []configuration.FileMutation{
			secretExecutorMutation(configTarget, []byte(
				`{"mcp":{"context7":{"apiKey":`+
					configuration.DeferredSecretJSONPlaceholder+`}}}`,
			)),
			secretExecutorMutation(registryTarget, []byte(
				`{"servers":{"context7":{"digest":"`+
					configuration.DeferredSecretDigestPlaceholder+`"}}}`,
			)),
		},
	}}
	plan, err := configuration.NewPreparedPlanWithMaterializations(
		transitions,
		nil,
		[]configuration.SecretMaterializationRecipe{{
			ResourceID:            resourceID,
			ConfigTarget:          configTarget,
			ConfigEntryPointer:    "/mcp/context7",
			ConfigValuePointer:    "/mcp/context7/apiKey",
			RegistryTarget:        registryTarget,
			RegistryDigestPointer: "/servers/context7/digest",
			SecretReference:       "CONTEXT7_FAKE_KEY",
		}},
	)
	if err != nil {
		t.Fatalf("NewPreparedPlanWithMaterializations() error = %v", err)
	}
	return Preview{
		Release:       ReleaseIdentity{ID: "release", IndexSHA256: testDigest("release")},
		Desired:       []domain.ComponentID{domain.ComponentAntigravity2},
		Plan:          domain.Plan{},
		Configuration: plan,
	}
}

func secretExecutorMutation(
	target domain.Location,
	content []byte,
) configuration.FileMutation {
	return configuration.FileMutation{
		Disposition: configuration.MutationPresent,
		Target:      target,
		After: configuration.AfterImage{
			Exists:  true,
			Content: content,
			Mode:    0o600,
		},
	}
}

func secretConfigTarget() domain.Location {
	return domain.Location{
		Root: domain.RootAntigravityData,
		Path: "mcp_config.json",
	}
}

func secretRegistryTarget() domain.Location {
	return domain.Location{
		Root: domain.RootAntigravityData,
		Path: "mainframe/mcp-ownership.json",
	}
}

func setDesiredConfigurationStates(
	t *testing.T,
	workspace *fakeConfigurationWorkspace,
	plan configuration.PreparedPlan,
	resolver configuration.SecretResolver,
) {
	t.Helper()
	materialized, err := plan.MaterializeSecrets(resolver)
	if err != nil {
		t.Fatalf("MaterializeSecrets() error = %v", err)
	}
	for index, mutation := range materialized.Transitions()[0].Mutations {
		workspace.public[mutation.Target] = configurationState(
			payloadDigest(mutation.After.Content),
			mutation.After.Mode,
			testIdentity(1, uint64(index+10)),
			testIdentity(1, uint64(index+20)),
		)
	}
}
