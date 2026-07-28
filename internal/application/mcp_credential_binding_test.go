package application

import (
	"errors"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestReviewResolvesNewMCPInstanceFromTheSameDesiredPlan(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	empty := applicationCredentialSnapshot(t, definitions, nil)
	snapshot := applicationOpenCodeMCPSnapshot(t)
	snapshot.Credentials = &empty
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	desired := applicationCredentialInstances(t, definitions)
	request := testRequest()
	request.Components = []domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentCodex,
		domain.ComponentOpenCode,
	}
	request.MCPSelections[0].Adapters = []domain.ComponentID{
		domain.ComponentOpenCode,
	}
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}
	request.CredentialInstances = &desired

	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if !reviewed.Applicable() {
		t.Fatal("same-plan MCP and credential creation was not applicable")
	}
	transitions := reviewed.Executable().Configuration.Transitions()
	if len(transitions) != 2 {
		t.Fatalf("combined transitions = %#v", transitions)
	}
	var openCodeAfter []byte
	for _, transition := range transitions {
		for _, mutation := range transition.Mutations {
			if mutation.Target.Path == "opencode.json" {
				openCodeAfter = mutation.After.Content
			}
		}
	}
	content := string(openCodeAfter)
	for _, value := range []string{
		`"CONTEXT7_API_KEY"`,
		`"{env:CONTEXT7_HOME_KEY}"`,
	} {
		if !strings.Contains(content, value) {
			t.Fatalf("OpenCode after-image omits %q: %s", value, content)
		}
	}
}

func TestOpenCodeContext7ApplicabilityRejectsForeignAdapterMutation(
	t *testing.T,
) {
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentOpenCode}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}
	semantic := lifecycle.Preview{
		MCP: mcpconfiguration.Plan{Intents: []mcpconfiguration.Intent{{
			ComponentID: domain.ComponentOpenCode,
			ServerID:    "context7",
		}}},
	}
	executable := executor.Preview{Plan: domain.Plan{
		Operations: []domain.Operation{{
			ComponentID: domain.ComponentClaudeCode,
			Kind:        domain.OperationRemove,
		}},
	}}

	if context7Applicable(request, semantic, executable) {
		t.Fatal("foreign adapter removal was considered applicable")
	}
}

func TestOpenCodeContext7ApplicabilityRejectsPreparationOnlyResource(
	t *testing.T,
) {
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentOpenCode}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}
	semantic := lifecycle.Preview{
		Configuration: configuration.Plan{
			Changes: []configuration.Change{{
				ResourceID:  "opencode.credentials-index",
				ComponentID: domain.ComponentOpenCode,
				Kind:        configuration.ChangeAdd,
			}},
		},
		MCP: mcpconfiguration.Plan{Intents: []mcpconfiguration.Intent{{
			ComponentID: domain.ComponentOpenCode,
			ServerID:    "context7",
		}}},
	}
	prepared, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs:     []string{"opencode.credentials-index"},
		PreparationOnly: true,
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "credentials-index.md",
			},
			After: configuration.AfterImage{
				Exists:  true,
				Content: []byte("# Credentials\n"),
				Mode:    0o600,
			},
		}},
	}})
	if err != nil {
		t.Fatalf("NewPreparedPlan() error = %v", err)
	}
	executable := executor.Preview{
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: domain.ComponentOpenCode,
			Kind:        domain.OperationInstall,
		}}},
		Configuration: prepared,
	}

	if context7Applicable(request, semantic, executable) {
		t.Fatal("preparation-only resource was considered applicable")
	}
}

func TestAntigravityContext7ApplicabilityIncludesKeylessAndRemoval(t *testing.T) {
	semantic := lifecycle.Preview{
		MCP: mcpconfiguration.Plan{Intents: []mcpconfiguration.Intent{{
			ComponentID: domain.ComponentAntigravity2,
			ServerID:    "context7",
		}}},
	}
	executable := executor.Preview{Plan: domain.Plan{
		Operations: []domain.Operation{{
			ComponentID: domain.ComponentAntigravity2,
			Kind:        domain.OperationInstall,
		}},
	}}
	keyless := Request{
		Components: []domain.ComponentID{domain.ComponentAntigravity2},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentAntigravity2},
		}},
	}
	removal := Request{
		Components: []domain.ComponentID{domain.ComponentAntigravity2},
	}

	if !context7Applicable(keyless, semantic, executable) {
		t.Fatal("keyless Antigravity Context7 change was not applicable")
	}
	if !context7Applicable(removal, semantic, executable) {
		t.Fatal("Antigravity Context7 removal was not applicable")
	}
}

func TestReviewAcceptsExactAntigravityContext7CredentialBinding(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	existing := applicationCredentialInstances(t, definitions)
	credentialSnapshot := applicationCredentialSnapshot(
		t,
		definitions,
		existing.All(),
	)
	snapshot := applicationAntigravityMCPSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentAntigravity2}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}

	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if !reviewed.Applicable() {
		t.Fatal("exact Antigravity Context7 plan was not applicable")
	}
	for _, transition := range reviewed.Executable().Configuration.Transitions() {
		for _, mutation := range transition.Mutations {
			content := string(mutation.After.Content)
			if strings.Contains(content, "application-fake-secret-value") {
				t.Fatal("reviewed after-image contains a secret value")
			}
			if mutation.Target.Root == domain.RootAntigravityConfig &&
				strings.Contains(content, "CONTEXT7_HOME_KEY") {
				t.Fatal("Antigravity configuration contains a secret reference")
			}
		}
	}
}

func TestReviewClonesMCPCredentialBindingProvenance(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	existing := applicationCredentialInstances(t, definitions)
	credentialSnapshot := applicationCredentialSnapshot(
		t,
		definitions,
		existing.All(),
	)
	snapshot := testSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentOpenCode}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}

	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	request.MCPCredentials[0].InstanceID = "changed-after-review"
	want := []MCPCredentialBinding{context7MCPBinding()}
	if !reflect.DeepEqual(reviewed.Request().MCPCredentials, want) {
		t.Fatalf(
			"reviewed MCP credentials = %#v, want %#v",
			reviewed.Request().MCPCredentials,
			want,
		)
	}
}

func TestResolveMCPSecretReusesOneInstanceAcrossSupportedAdapters(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	existing := applicationCredentialInstances(t, definitions)
	credentials := applicationCredentialSnapshot(
		t,
		definitions,
		existing.All(),
	)
	request := Request{
		Components: []domain.ComponentID{
			domain.ComponentOpenCode,
			domain.ComponentAntigravity2,
		},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters: []domain.ComponentID{
				domain.ComponentOpenCode,
				domain.ComponentAntigravity2,
			},
		}},
		MCPCredentials: []MCPCredentialBinding{
			{
				ComponentID: domain.ComponentOpenCode,
				ServerID:    "context7", ProfileID: "remote-api-key",
				InstanceID: "context7-home",
			},
			{
				ComponentID: domain.ComponentAntigravity2,
				ServerID:    "context7", ProfileID: "remote-api-key",
				InstanceID: "context7-home",
			},
		},
	}

	resolved, err := resolveMCPCredentials(
		Snapshot{Credentials: &credentials},
		request,
	)
	if err != nil {
		t.Fatalf("resolveMCPCredentials() error = %v", err)
	}
	if len(resolved) != 2 ||
		resolved[0].ComponentID != domain.ComponentOpenCode ||
		resolved[1].ComponentID != domain.ComponentAntigravity2 {
		t.Fatalf("resolved bindings = %#v", resolved)
	}
	if resolved[0].EnvironmentVariable != resolved[1].EnvironmentVariable {
		t.Fatalf("shared instance resolved to different references: %#v", resolved)
	}
}

func TestApplyConfirmedRevalidatesLockedMCPCredentialBinding(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	existing := applicationCredentialInstances(t, definitions)
	initial := applicationOpenCodeMCPSnapshot(t)
	initialCredentials := applicationCredentialSnapshot(
		t,
		definitions,
		existing.All(),
	)
	initial.Credentials = &initialCredentials
	missing := applicationOpenCodeMCPSnapshot(t)
	missingCredentials := applicationCredentialSnapshot(t, definitions, nil)
	missing.Credentials = &missingCredentials
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{initial, missing}}
	session := &fakeApplySession{refresh: true}
	service, err := New(
		builder,
		&fakeApplyExecutorFactory{session: session},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	request := testRequest()
	request.Components = []domain.ComponentID{domain.ComponentOpenCode}
	request.MCPSelections[0].Adapters = request.Components
	request.MCPCredentials = []MCPCredentialBinding{context7MCPBinding()}
	reviewed, err := service.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	if _, err := service.ApplyConfirmed(reviewed); err == nil {
		t.Fatal("ApplyConfirmed() ignored a missing bound instance during refresh")
	}
	if session.nonRecoveringApplies != 1 || session.applies != 0 ||
		session.closes != 1 {
		t.Fatalf(
			"non-recovering/recovering/closes = %d/%d/%d",
			session.nonRecoveringApplies,
			session.applies,
			session.closes,
		)
	}
	if len(builder.requests) != 2 ||
		!reflect.DeepEqual(builder.requests[0], builder.requests[1]) {
		t.Fatalf("locked refresh requests = %#v", builder.requests)
	}
}

func TestApplyConfirmedUsesExactPlanPathAndSurfacesWarnings(t *testing.T) {
	definitions := applicationCredentialDefinitions(t)
	credentialSnapshot := applicationCredentialSnapshot(t, definitions, nil)
	snapshot := testSnapshot(t)
	snapshot.Credentials = &credentialSnapshot
	session := &fakeApplySession{
		result:   executor.Result{Warnings: []string{"executor warning"}},
		closeErr: errors.New("close warning"),
	}
	apply := &fakeApplyExecutorFactory{session: session}
	recovery := &fakeRecoveryExecutorFactory{session: &fakeRecoverySession{}}
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{snapshot}},
		apply,
		recovery,
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	desired := applicationCredentialInstances(t, definitions)
	reviewed, err := service.Review(Request{
		CredentialInstances: &desired,
	})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}

	result, err := service.ApplyConfirmed(reviewed)
	if err != nil {
		t.Fatalf("ApplyConfirmed() error = %v", err)
	}
	if recovery.opens != 0 || session.nonRecoveringApplies != 1 ||
		session.applies != 0 {
		t.Fatalf(
			"recovery/non-recovering/recovering = %d/%d/%d",
			recovery.opens,
			session.nonRecoveringApplies,
			session.applies,
		)
	}
	want := []string{"executor warning", "close apply executor: close warning"}
	if !reflect.DeepEqual(result.Warnings, want) {
		t.Fatalf("warnings = %#v, want %#v", result.Warnings, want)
	}
}

func TestReviewDoesNotEnableConfirmedApplyForOtherAdapterPlans(t *testing.T) {
	service, err := New(
		&fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}},
		&fakeApplyExecutorFactory{},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	if reviewed.Applicable() {
		t.Fatal("confirmed apply widened beyond the OpenCode Context7 slice")
	}
}

func applicationCredentialInstances(
	t *testing.T,
	definitions credentialcatalog.Definitions,
) credentialcatalog.Instances {
	t.Helper()
	instances, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{applicationCredentialInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	return instances
}

func applicationCredentialSnapshot(
	t *testing.T,
	definitions credentialcatalog.Definitions,
	instances []credentialcatalog.Instance,
) credentialcatalog.InstanceSnapshot {
	t.Helper()
	if instances == nil {
		snapshot, err := credentialcatalog.ObserveInstances(
			applicationCredentialHost{},
			definitions,
		)
		if err != nil {
			t.Fatalf("ObserveInstances() error = %v", err)
		}
		return snapshot
	}
	built, err := credentialcatalog.BuildInstances(instances, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	payload, err := credentialcatalog.EncodeInstances(built)
	if err != nil {
		t.Fatalf("EncodeInstances() error = %v", err)
	}
	snapshot, err := credentialcatalog.ObserveInstances(
		staticCredentialHost{content: payload},
		definitions,
	)
	if err != nil {
		t.Fatalf("ObserveInstances() error = %v", err)
	}
	return snapshot
}

func context7MCPBinding() MCPCredentialBinding {
	return MCPCredentialBinding{
		ServerID: "context7", ProfileID: "remote-api-key",
		InstanceID: "context7-home",
	}
}

func applicationOpenCodeMCPSnapshot(t *testing.T) Snapshot {
	t.Helper()
	host := applicationCredentialHost{}
	base, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	catalog := applicationMCPCatalog(t)
	mcp, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{applicationOpenCodeProjection()},
		catalog,
		host,
	)
	if err != nil {
		t.Fatalf("mcpconfiguration.Inspect() error = %v", err)
	}
	model, err := installmodel.New(
		[]installmodel.ComponentSpec{
			{ID: domain.ComponentClaudeCode},
			{ID: domain.ComponentCodex},
			{ID: domain.ComponentOpenCode},
			{ID: domain.ComponentAntigravity2},
			{ID: domain.ComponentCodexGates},
		},
	)
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	service, err := lifecycle.NewWithInspections(
		model,
		domain.ObservedState{},
		base,
		mcp,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspections() error = %v", err)
	}
	return Snapshot{Release: testReleaseIdentity(), Lifecycle: service}
}

func applicationAntigravityMCPSnapshot(t *testing.T) Snapshot {
	t.Helper()
	return applicationMCPSnapshot(t, applicationAntigravityProjection())
}

func applicationMCPSnapshot(
	t *testing.T,
	projection releasecontract.MCPProjection,
) Snapshot {
	t.Helper()
	host := applicationCredentialHost{}
	base, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	catalog := applicationMCPCatalog(t)
	mcp, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection},
		catalog,
		host,
	)
	if err != nil {
		t.Fatalf("mcpconfiguration.Inspect() error = %v", err)
	}
	model, err := applicationMCPInstallModel()
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	service, err := lifecycle.NewWithInspections(
		model,
		domain.ObservedState{},
		base,
		mcp,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspections() error = %v", err)
	}
	return Snapshot{Release: testReleaseIdentity(), Lifecycle: service}
}

func applicationMCPInstallModel() (installmodel.Model, error) {
	return installmodel.New(
		[]installmodel.ComponentSpec{
			{ID: domain.ComponentClaudeCode},
			{ID: domain.ComponentCodex},
			{ID: domain.ComponentOpenCode},
			{ID: domain.ComponentAntigravity2},
			{ID: domain.ComponentCodexGates},
		},
	)
}

func applicationAntigravityProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "antigravity-2.mcp.context7", ComponentID: domain.ComponentAntigravity2,
		Codec:    releasecontract.MCPProjectionAntigravityGlobalHTTP,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootAntigravityConfig, Path: "mcp_config.json",
		},
		MapPointer: "/mcpServers", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootAntigravityData,
			Path: "mainframe/mcp-ownership.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"serverUrl":"https://mcp.context7.com/mcp"}`,
	}
}

func applicationMCPCatalog(t *testing.T) mcpcatalog.Catalog {
	t.Helper()
	payload, err := os.ReadFile("../mcpcatalog/catalog.json")
	if err != nil {
		t.Fatalf("read MCP catalog: %v", err)
	}
	catalog, err := mcpcatalog.Parse(payload)
	if err != nil {
		t.Fatalf("parse MCP catalog: %v", err)
	}
	return catalog
}

func applicationOpenCodeProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID: "opencode.mcp.context7", ComponentID: domain.ComponentOpenCode,
		Codec:    releasecontract.MCPProjectionOpenCodeRemote,
		ServerID: "context7", ProfileID: "remote-keyless",
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "opencode.json",
		},
		MapPointer: "/mcp", EntryKey: "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json.mainframe-mcp.json",
		},
		RegistrySchemaVersion: 1, RegistryEntriesPointer: "/servers",
		DesiredEntry: `{"type":"remote","url":"https://mcp.context7.com/mcp"}`,
	}
}

type staticCredentialHost struct {
	content []byte
}

func (host staticCredentialHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	return hostfs.Entry{
		Kind: hostfs.EntryRegular, Mode: 0o600,
		Content: append([]byte(nil), host.content...),
	}, nil
}
