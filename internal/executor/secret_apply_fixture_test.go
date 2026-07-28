package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

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

func secretFileExecutorPreview(t *testing.T) Preview {
	t.Helper()
	configTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "opencode.json",
	}
	fileTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "mainframe/secrets/context7-api-key",
	}
	registryTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: "opencode.json.mainframe-mcp.json",
	}
	resourceID := "opencode.mcp.context7"
	transitions := []configuration.Transition{{
		ResourceIDs: []string{resourceID},
		Mutations: []configuration.FileMutation{
			secretExecutorMutation(
				fileTarget,
				[]byte(configuration.DeferredSecretFilePlaceholder),
			),
			secretExecutorMutation(
				configTarget,
				[]byte(`{"mcp":{"context7":{"headers":{"CONTEXT7_API_KEY":"{file:mainframe/secrets/context7-api-key}"}}}}`),
			),
			secretExecutorMutation(
				registryTarget,
				[]byte(`{"servers":{"context7":{"secret_file_sha256":"`+
					configuration.DeferredSecretDigestPlaceholder+`"}}}`),
			),
		},
	}}
	plan, err := configuration.NewPreparedPlanWithMaterializations(
		transitions,
		nil,
		[]configuration.SecretMaterializationRecipe{{
			ResourceID:            resourceID,
			FileTarget:            fileTarget,
			RegistryTarget:        registryTarget,
			RegistryDigestPointer: "/servers/context7/secret_file_sha256",
			SecretReference:       "CONTEXT7_FAKE_KEY",
		}},
	)
	if err != nil {
		t.Fatal(err)
	}
	return Preview{
		Release: ReleaseIdentity{
			ID:          "release",
			IndexSHA256: testDigest("release"),
		},
		Desired:       []domain.ComponentID{domain.ComponentOpenCode},
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
