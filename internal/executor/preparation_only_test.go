package executor

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestMaterializeConfigurationsRejectsPreparationOnlyTransition(t *testing.T) {
	target := domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: "secrets.env",
	}
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs:     []string{"credential-tools.secrets-store"},
		PreparationOnly: true,
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      target,
			After: configuration.AfterImage{
				Exists: true, Content: []byte{}, Mode: 0o600,
			},
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}

	_, err = (Executor{}).materializeConfigurations(plan)
	if err == nil || !strings.Contains(err.Error(), "preparation-only") {
		t.Fatalf("materializeConfigurations() error = %v", err)
	}
}

func TestCollapseConfigurationNoOpsPreservesPreparationOnly(t *testing.T) {
	target := domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: "secrets.env",
	}
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs:     []string{"credential-tools.secrets-store"},
		PreparationOnly: true,
		Mutations: []configuration.FileMutation{{
			Disposition: configuration.MutationPresent,
			Target:      target,
			After: configuration.AfterImage{
				Exists: true, Content: []byte{}, Mode: 0o600,
			},
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}
	executor := Executor{
		configurations: newFakeConfigurationWorkspace(&fakeStore{}),
	}
	collapsed, err := executor.collapseConfigurationNoOps(plan)
	if err != nil {
		t.Fatal(err)
	}
	if !collapsed.HasPreparationOnly() {
		t.Fatal("collapseConfigurationNoOps() cleared PreparationOnly")
	}
}
