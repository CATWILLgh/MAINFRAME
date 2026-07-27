package main

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestDraftCommitmentIsStableAndBindsExecutablePlan(t *testing.T) {
	preview := draftCommitmentPreview(t, []byte(`{"value":"after"}`))
	scope := draftCommitmentScope{
		WorkingDirectory: "/work",
		ReleaseRoot:      "/release",
		SourceRoot:       "/release/bundles",
		TransactionState: "/state",
		Targets: []draftCommitmentTarget{{
			Root: domain.RootOpenCodeConfig, Path: "/config/opencode",
		}},
	}
	desired := draftDesiredState{
		Adapters:          []domain.ComponentID{domain.ComponentOpenCode},
		MCP:               []draftMCPSelection{},
		DiagnosticsPolicy: draftDiagnosticsPolicy,
	}

	first, err := draftReviewCommitment(desired, preview, scope)
	if err != nil {
		t.Fatalf("draftReviewCommitment() error = %v", err)
	}
	again, err := draftReviewCommitment(desired, preview, scope)
	if err != nil || first != again {
		t.Fatalf("repeat commitment = %q, %v; want %q", again, err, first)
	}
	if !strings.HasPrefix(first, "sha256:") {
		t.Fatalf("commitment = %q", first)
	}
	for _, test := range draftCommitmentMutationCases(t) {
		t.Run(test.name, func(t *testing.T) {
			assertDraftCommitmentMutation(
				t,
				first,
				desired,
				preview,
				scope,
				test.change,
			)
		})
	}
}

type draftCommitmentMutationCase struct {
	name   string
	change draftCommitmentMutator
}

func draftCommitmentMutationCases(
	t *testing.T,
) []draftCommitmentMutationCase {
	return []draftCommitmentMutationCase{
		{name: "desired", change: func(
			desired *draftDesiredState,
			_ *executor.Preview,
			_ *draftCommitmentScope,
		) {
			desired.Adapters = []domain.ComponentID{domain.ComponentAntigravity2}
		}},
		{name: "release", change: func(
			_ *draftDesiredState,
			preview *executor.Preview,
			_ *draftCommitmentScope,
		) {
			preview.Release.ID = "changed-release"
		}},
		{name: "scope", change: func(
			_ *draftDesiredState,
			_ *executor.Preview,
			scope *draftCommitmentScope,
		) {
			scope.WorkingDirectory = "/changed-work"
		}},
		{name: "operation", change: func(
			_ *draftDesiredState,
			preview *executor.Preview,
			_ *draftCommitmentScope,
		) {
			preview.Plan.Operations[0].SourcePath = "bundles/changed"
		}},
		{name: "before image", change: mutateDraftBeforeImage(t)},
		{name: "after image", change: mutateDraftAfterImage(t)},
		{name: "precondition", change: mutateDraftPrecondition(t)},
		{name: "materialization", change: mutateDraftMaterialization(t)},
	}
}

func assertDraftCommitmentMutation(
	t *testing.T,
	first string,
	desired draftDesiredState,
	preview executor.Preview,
	scope draftCommitmentScope,
	change draftCommitmentMutator,
) {
	t.Helper()
	changedDesired := desired
	changedDesired.Adapters = append(
		[]domain.ComponentID(nil),
		desired.Adapters...,
	)
	changedPreview := preview
	changedPreview.Plan.Operations = append(
		[]domain.Operation(nil),
		preview.Plan.Operations...,
	)
	changedScope := scope
	changedScope.Targets = append(
		[]draftCommitmentTarget(nil),
		scope.Targets...,
	)
	change(&changedDesired, &changedPreview, &changedScope)
	second, err := draftReviewCommitment(
		changedDesired,
		changedPreview,
		changedScope,
	)
	if err != nil {
		t.Fatalf("changed commitment error = %v", err)
	}
	if first == second {
		t.Fatal("changed field did not change commitment")
	}
}

func draftCommitmentPreview(
	t *testing.T,
	after []byte,
) executor.Preview {
	t.Helper()
	prepared := draftCommitmentPreparedPlan(t, after)
	return executor.Preview{
		Release: executor.ReleaseIdentity{
			ID:          "release",
			IndexSHA256: strings.Repeat("2", 64),
		},
		Desired: []domain.ComponentID{domain.ComponentOpenCode},
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: domain.ComponentOpenCode,
			UnitID:      "opencode.bundle",
			Kind:        domain.OperationInstall,
			Artifact: domain.Artifact{
				Location: domain.Location{
					Root: domain.RootOpenCodeConfig,
					Path: "bundle",
				},
			},
			SourcePath: "bundles/opencode",
		}}},
		Configuration: prepared,
	}
}

func draftCommitmentPreparedPlan(
	t *testing.T,
	after []byte,
) configuration.PreparedPlan {
	t.Helper()
	prepared, err := configuration.NewPreparedPlanWithMaterializations(
		draftCommitmentTransitions(after),
		draftCommitmentPreconditions(),
		draftCommitmentMaterializations(),
	)
	if err != nil {
		t.Fatalf("NewPreparedPlan() error = %v", err)
	}
	return prepared
}

func draftCommitmentTransitions(
	after []byte,
) []configuration.Transition {
	return []configuration.Transition{{
		ResourceIDs: []string{"opencode.config"},
		Mutations:   draftCommitmentMutations(after),
	}}
}

func draftCommitmentMutations(
	after []byte,
) []configuration.FileMutation {
	return []configuration.FileMutation{{
		Disposition: configuration.MutationPresent,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json",
		},
		Before: configuration.BeforeImage{
			Exists: true,
			SHA256: strings.Repeat("1", 64),
			Mode:   0o600,
			Device: 1, Inode: 2,
			BirthSeconds: 3,
		},
		After: configuration.AfterImage{
			Exists: true,
			Content: []byte(
				`{"mcp":{"headers":{"key":"$MAINFRAME_DEFERRED_SECRET_VALUE"}}}`,
			),
			Mode: 0o600,
		},
	}, {
		Disposition: configuration.MutationPresent,
		Target: domain.Location{
			Root: domain.RootCredentialsConfig,
			Path: "registry.json",
		},
		After: configuration.AfterImage{
			Exists: true,
			Content: []byte(
				`{"servers":{"context7":{"digest":"$MAINFRAME_DEFERRED_SECRET_DIGEST"}}}`,
			),
			Mode: 0o600,
		},
	}, {
		Disposition: configuration.MutationPresent,
		Target: domain.Location{
			Root: domain.RootHome,
			Path: ".mainframe-extra.json",
		},
		After: configuration.AfterImage{
			Exists: true, Content: after, Mode: 0o600,
		},
	}}
}

func draftCommitmentPreconditions() []configuration.ReadPrecondition {
	return []configuration.ReadPrecondition{{
		Kind: configuration.ReadPreconditionSymlink,
		Target: domain.Location{
			Root: domain.RootHome,
			Path: ".mainframe-link",
		},
		Device: 3, Inode: 4, BirthSeconds: 5,
		ExpectedTargetPath: "/expected/target",
	}}
}

func draftCommitmentMaterializations() []configuration.SecretMaterializationRecipe {
	return []configuration.SecretMaterializationRecipe{{
		ResourceID: "opencode.config",
		ConfigTarget: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json",
		},
		ConfigEntryPointer: "/mcp",
		ConfigValuePointer: "/mcp/headers/key",
		RegistryTarget: domain.Location{
			Root: domain.RootCredentialsConfig,
			Path: "registry.json",
		},
		RegistryDigestPointer: "/servers/context7/digest",
		SecretReference:       "CONTEXT7_HOME_KEY",
	}}
}

type draftCommitmentMutator func(
	*draftDesiredState,
	*executor.Preview,
	*draftCommitmentScope,
)

func mutateDraftBeforeImage(t *testing.T) draftCommitmentMutator {
	return func(
		_ *draftDesiredState,
		preview *executor.Preview,
		_ *draftCommitmentScope,
	) {
		transitions := preview.Configuration.Transitions()
		for index := range transitions[0].Mutations {
			if transitions[0].Mutations[index].Before.Exists {
				transitions[0].Mutations[index].Before.Inode++
			}
		}
		preview.Configuration = rebuildDraftPrepared(t, preview, transitions)
	}
}

func mutateDraftAfterImage(t *testing.T) draftCommitmentMutator {
	return func(
		_ *draftDesiredState,
		preview *executor.Preview,
		_ *draftCommitmentScope,
	) {
		transitions := preview.Configuration.Transitions()
		for index := range transitions[0].Mutations {
			if transitions[0].Mutations[index].Target.Root == domain.RootHome {
				transitions[0].Mutations[index].After.Content =
					[]byte(`{"changed":true}`)
			}
		}
		preview.Configuration = rebuildDraftPrepared(t, preview, transitions)
	}
}

func mutateDraftPrecondition(t *testing.T) draftCommitmentMutator {
	return func(
		_ *draftDesiredState,
		preview *executor.Preview,
		_ *draftCommitmentScope,
	) {
		preconditions := preview.Configuration.Preconditions()
		preconditions[0].ExpectedTargetPath = "/changed/target"
		prepared, err := configuration.NewPreparedPlanWithMaterializations(
			preview.Configuration.Transitions(),
			preconditions,
			preview.Configuration.Materializations(),
		)
		if err != nil {
			t.Fatal(err)
		}
		preview.Configuration = prepared
	}
}

func mutateDraftMaterialization(t *testing.T) draftCommitmentMutator {
	return func(
		_ *draftDesiredState,
		preview *executor.Preview,
		_ *draftCommitmentScope,
	) {
		materializations := preview.Configuration.Materializations()
		materializations[0].SecretReference = "CONTEXT7_WORK_KEY"
		prepared, err := configuration.NewPreparedPlanWithMaterializations(
			preview.Configuration.Transitions(),
			preview.Configuration.Preconditions(),
			materializations,
		)
		if err != nil {
			t.Fatal(err)
		}
		preview.Configuration = prepared
	}
}

func rebuildDraftPrepared(
	t *testing.T,
	preview *executor.Preview,
	transitions []configuration.Transition,
) configuration.PreparedPlan {
	t.Helper()
	prepared, err := configuration.NewPreparedPlanWithMaterializations(
		transitions,
		preview.Configuration.Preconditions(),
		preview.Configuration.Materializations(),
	)
	if err != nil {
		t.Fatal(err)
	}
	return prepared
}
