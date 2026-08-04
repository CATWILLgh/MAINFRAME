package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPrepareJSONClaimRemovalCreatesNoStagingPayload(t *testing.T) {
	fixture := newFixture(Preview{})
	configurations := newFakeConfigurationWorkspace(fixture.store)
	executor := fixture.configurationExecutor(configurations)
	prepared, err := executor.materializeConfigurations(
		preparedJSONClaimRemovalPlan(t),
	)
	if err != nil {
		t.Fatalf("materializeConfigurations() error = %v", err)
	}
	mutation := prepared.transitions[0].Mutations[0]
	if mutation.Disposition != ConfigurationRemoveJSONClaimFile ||
		len(prepared.payloads) != 0 {
		t.Fatalf("prepared JSON claim removal = %#v", mutation)
	}
}

func preparedJSONClaimRemovalPlan(t *testing.T) configuration.PreparedPlan {
	t.Helper()
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{"zcode.hooks"},
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationRemoveJSONClaimFile,
			Target: domain.Location{
				Root: domain.RootZCodeConfig, Path: "cli/config.json",
			},
			Before: configuration.BeforeImage{
				Exists: true, SHA256: testDigest("before"), Mode: 0o600,
				Device: 1, Inode: 2, BirthSeconds: 3,
			},
			After: configuration.AfterImage{},
		}},
	}})
	if err != nil {
		t.Fatalf("NewPreparedPlan() error = %v", err)
	}
	return plan
}
