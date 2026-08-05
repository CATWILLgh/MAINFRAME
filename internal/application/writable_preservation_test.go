package application

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func TestExecutableFilesystemPlanOmitsPreservationOperations(t *testing.T) {
	preserve := domain.Operation{
		ComponentID: domain.ComponentZCodeDesktop, UnitID: "zcode.agent",
		Kind: domain.OperationPreserve,
		Artifact: domain.Artifact{
			Location:        domain.Location{Root: domain.RootZCodeConfig, Path: "agents/agent.md"},
			Ownership:       domain.OwnershipManagedDrifted,
			Materialization: domain.MaterializationWritableFile,
		},
	}
	replace := domain.Operation{
		ComponentID: domain.ComponentZCodeDesktop, UnitID: "zcode.other",
		Kind:       domain.OperationReplace,
		Artifact:   domain.Artifact{Location: domain.Location{Root: domain.RootZCodeConfig, Path: "agents/other.md"}},
		SourcePath: "zcode/agents/other.md",
	}
	semantic := domain.Plan{Operations: []domain.Operation{preserve, replace}}

	executable := executableFilesystemPlan(semantic)
	if len(executable.Operations) != 1 || executable.Operations[0] != replace {
		t.Fatalf("executable plan = %#v, want only replace", executable)
	}
	if len(semantic.Operations) != 2 || semantic.Operations[0] != preserve {
		t.Fatalf("semantic plan was mutated: %#v", semantic)
	}
	if got := executableFilesystemPlan(domain.Plan{Operations: []domain.Operation{preserve}}); len(got.Operations) != 0 {
		t.Fatalf("preserve-only executable plan = %#v, want empty", got)
	}
	if zcodeLifecycleApplicable(
		Request{Components: []domain.ComponentID{domain.ComponentZCodeDesktop}},
		lifecycle.Preview{Filesystem: domain.Plan{Operations: []domain.Operation{preserve}}},
		executor.Preview{},
	) {
		t.Fatal("preserve-only preview is applicable despite having no executable work")
	}
}

func TestReviewKeepsPreservationVisibleAndOtherWorkApplicable(t *testing.T) {
	snapshot := writablePreservationSnapshot(t)
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{snapshot, snapshot}}
	session := &fakeApplySession{refresh: true}
	factory := &fakeApplyExecutorFactory{session: session}
	service, err := New(builder, factory, readyRecoveryFactory())
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(Request{Components: []domain.ComponentID{domain.ComponentZCodeDesktop}})
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	semantic := reviewed.Semantic().Filesystem.Operations
	if len(semantic) != 2 || semantic[0].Kind != domain.OperationPreserve ||
		semantic[1].Kind != domain.OperationReplace {
		t.Fatalf("semantic operations = %#v", semantic)
	}
	executable := reviewed.Executable().Plan.Operations
	if len(executable) != 1 || executable[0].Kind != domain.OperationReplace {
		t.Fatalf("executable operations = %#v", executable)
	}
	if !reviewed.Applicable() {
		t.Fatal("mixed preserve and replace plan is not applicable")
	}
	if _, err := service.Apply(reviewed); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if !reflect.DeepEqual(session.fresh.Plan.Operations, executable) {
		t.Fatalf("refreshed executable operations = %#v", session.fresh.Plan.Operations)
	}
}

func writablePreservationSnapshot(t *testing.T) Snapshot {
	t.Helper()
	const digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	drifted := domain.Location{Root: domain.RootZCodeConfig, Path: "agents/drifted.md"}
	previous := domain.Location{Root: domain.RootZCodeConfig, Path: "agents/previous.md"}
	model, err := installmodel.New([]installmodel.ComponentSpec{{
		ID: domain.ComponentZCodeDesktop,
		Artifacts: []installmodel.ArtifactSpec{
			{UnitID: "zcode.drifted", Materialization: domain.MaterializationWritableFile, Target: drifted, SourcePath: "agents/drifted.md", SourceSHA256: digest},
			{UnitID: "zcode.previous", Materialization: domain.MaterializationWritableFile, Target: previous, SourcePath: "agents/previous.md", SourceSHA256: digest},
		},
	}})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	observed := domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: domain.ComponentZCodeDesktop,
		Artifacts: []domain.Artifact{
			{Location: drifted, UnitID: "zcode.drifted", Ownership: domain.OwnershipManagedDrifted, Materialization: domain.MaterializationWritableFile, ContentSHA256: digest, Mode: 0o600},
			{Location: previous, UnitID: "zcode.previous", Ownership: domain.OwnershipManagedPrevious, Materialization: domain.MaterializationWritableFile, ContentSHA256: digest, Mode: 0o600},
		},
	}}}
	service, err := lifecycle.New(model, observed)
	if err != nil {
		t.Fatalf("lifecycle.New() error = %v", err)
	}
	return Snapshot{Release: testReleaseIdentity(), Lifecycle: service}
}
