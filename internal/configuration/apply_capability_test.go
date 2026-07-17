package configuration_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectionAcceptsSupportedOpenCodePermissionApply(t *testing.T) {
	resource := supportedOpenCodePermissionResource()

	if _, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		&fakeHost{},
	); err != nil {
		t.Fatalf("Inspect() rejected supported apply: %v", err)
	}
}

func TestInspectionRejectsSupportedApplyForOtherComponents(t *testing.T) {
	resource := supportedOpenCodePermissionResource()
	resource.ComponentID = domain.ComponentCodex

	if _, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		&fakeHost{},
	); err == nil {
		t.Fatal("Inspect() accepted supported apply for another component")
	}
}

func TestInspectionPrepareRejectsUnadvertisedOwnedMapApply(t *testing.T) {
	resource := supportedOpenCodePermissionResource()
	resource.Apply = releasecontract.SupportUnimplemented
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		&fakeHost{},
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}

	prepared, err := inspection.Prepare([]domain.ComponentID{domain.ComponentOpenCode})
	if err == nil || len(prepared.Transitions()) != 0 {
		t.Fatalf("Prepare() = %#v, %v; want error and zero plan", prepared, err)
	}
}

func supportedOpenCodePermissionResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "opencode.permissions",
		ComponentID: domain.ComponentOpenCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "opencode.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportSupported,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer: "/permission", EntrySchema: "decision-rule-v1",
			DesiredMap: `{"bash":{"*":"deny"}}`,
			RegistryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-permissions.json",
			},
			RegistrySchemaVersion: 1,
			EntriesPointer:        "/actions",
		},
	}
}
