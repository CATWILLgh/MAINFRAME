package releasecontract_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestManagedMCPRegistryContractsAreCompleteAndDeterministic(t *testing.T) {
	want := []releasecontract.ManagedMCPRegistryContract{
		{
			ComponentID: domain.ComponentAntigravity2,
			RegistryTarget: domain.Location{
				Root: domain.RootAntigravityData,
				Path: "mainframe/mcp-ownership.json",
			},
		},
		{
			ComponentID: domain.ComponentClaudeCode,
			RegistryTarget: domain.Location{
				Root: domain.RootClaudeConfig,
				Path: "mainframe/mcp-ownership.json",
			},
		},
		{
			ComponentID: domain.ComponentCodex,
			RegistryTarget: domain.Location{
				Root: domain.RootCodexConfig,
				Path: "mainframe/mcp-ownership.json",
			},
		},
		{
			ComponentID: domain.ComponentOpenCode,
			RegistryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-mcp.json",
			},
		},
	}

	first := releasecontract.ManagedMCPRegistryContracts()
	second := releasecontract.ManagedMCPRegistryContracts()
	if !reflect.DeepEqual(first, want) {
		t.Fatalf("contracts = %#v, want %#v", first, want)
	}
	if !reflect.DeepEqual(second, want) {
		t.Fatalf("repeated contracts = %#v, want %#v", second, want)
	}
	first[0].ComponentID = domain.ComponentCodex
	if reflect.DeepEqual(releasecontract.ManagedMCPRegistryContracts(), first) {
		t.Fatal("caller mutated the shared registry contract")
	}
}
