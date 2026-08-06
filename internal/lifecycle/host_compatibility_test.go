package lifecycle

import (
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestSelectingAnIncompatibleComponentReturnsATypedHostRequirementError(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	service, err := service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID:      domain.ComponentAntigravity2,
		Status:           hostcompatibility.StatusIncompatible,
		DetectedVersions: []string{"2.5.0"},
		ExpectedVersions: []string{"2.2.1"},
	}})
	if err != nil {
		t.Fatalf("WithHostCompatibility() error = %v", err)
	}

	_, err = service.Plan([]domain.ComponentID{domain.ComponentAntigravity2})

	var hostRequirement ComponentHostRequirementError
	if !errors.As(err, &hostRequirement) {
		t.Fatalf("Plan() error = %v, want a ComponentHostRequirementError", err)
	}
	if hostRequirement.Component != domain.ComponentAntigravity2 {
		t.Fatalf("component = %q", hostRequirement.Component)
	}
}

func TestIncompatibleInstalledTargetIsVisibleUnselectedAndPreserved(t *testing.T) {
	observed := domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: domain.ComponentAntigravity2,
		Artifacts: []domain.Artifact{
			artifact(domain.RootAntigravityConfig, "plugins/mainframe", domain.OwnershipManagedExact),
		},
	}}}
	service := newTestService(t, observed)
	service, err := service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID:      domain.ComponentAntigravity2,
		Status:           hostcompatibility.StatusIncompatible,
		DetectedVersions: []string{"2.1.0"},
		ExpectedVersions: []string{"2.2.1"},
	}})
	if err != nil {
		t.Fatalf("WithHostCompatibility() error = %v", err)
	}

	target := service.Targets()[3]
	if target.Selected || target.HostCompatibility == nil ||
		target.HostCompatibility.Status != hostcompatibility.StatusIncompatible {
		t.Fatalf("target = %#v", target)
	}
	plan, err := service.Plan([]domain.ComponentID{domain.ComponentClaudeCode})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	for _, operation := range plan.Operations {
		if operation.ComponentID == domain.ComponentAntigravity2 {
			t.Fatalf("incompatible target operation = %#v", operation)
		}
	}
}

func TestLifecycleRejectsExplicitIncompatibleSelection(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	service, err := service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID: domain.ComponentAntigravity2,
		Status:      hostcompatibility.StatusMissing,
	}})
	if err != nil {
		t.Fatalf("WithHostCompatibility() error = %v", err)
	}
	_, err = service.Plan([]domain.ComponentID{domain.ComponentAntigravity2})
	if err == nil || !strings.Contains(err.Error(), "host requirement") {
		t.Fatalf("Plan() error = %v", err)
	}
}

func TestCompatibleInstalledTargetKeepsItsDefaultSelection(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{{
		ID: domain.ComponentAntigravity2,
		Artifacts: []domain.Artifact{
			artifact(domain.RootAntigravityConfig, "plugins/mainframe", domain.OwnershipManagedExact),
		},
	}}})
	service, err := service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID: domain.ComponentAntigravity2,
		Status:      hostcompatibility.StatusSatisfied,
	}})
	if err != nil {
		t.Fatal(err)
	}
	target := service.Targets()[3]
	if !target.Selected || target.Status != StatusManaged {
		t.Fatalf("target = %#v", target)
	}
}

func TestCompatibilityPreservationFiltersFallbackConfiguration(t *testing.T) {
	resource := releasecontract.Resource{
		ID: "antigravity.settings", ComponentID: domain.ComponentAntigravity2,
		Strategy:    releasecontract.StrategySeedIfAbsent,
		Observation: releasecontract.SupportUnimplemented,
		Apply:       releasecontract.SupportUnimplemented,
	}
	service, err := NewWithResources(
		testModel(t),
		domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: domain.ComponentAntigravity2,
			Artifacts: []domain.Artifact{
				artifact(domain.RootAntigravityConfig, "plugins/mainframe", domain.OwnershipManagedExact),
			},
		}}},
		[]releasecontract.Resource{resource},
	)
	if err != nil {
		t.Fatal(err)
	}
	service, err = service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID: domain.ComponentAntigravity2,
		Status:      hostcompatibility.StatusUnavailable,
	}})
	if err != nil {
		t.Fatal(err)
	}
	preview, err := service.Preview(PreviewRequest{Components: []domain.ComponentID{domain.ComponentClaudeCode}})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if !reflect.DeepEqual(preview.Configuration, configuration.Plan{}) {
		t.Fatalf("configuration = %#v, want empty", preview.Configuration)
	}
}

func TestCompatibilityPreservationFiltersMCPPreviewAndPreparation(t *testing.T) {
	service := incompatibleAntigravityMCPService(t)
	request := PreviewRequest{Components: []domain.ComponentID{domain.ComponentClaudeCode}}
	preview, err := service.Preview(request)
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.MCP.Intents) != 0 || len(preview.MCP.Migrations) != 0 || preview.MCP.Blocking {
		t.Fatalf("preserved MCP preview = %#v", preview.MCP)
	}
	prepared, err := service.PrepareConfiguration(request)
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("preserved MCP transitions = %#v", prepared.Transitions())
	}
}

func incompatibleAntigravityMCPService(t *testing.T) Service {
	t.Helper()
	projection := lifecycleAntigravityProjection()
	host := lifecyclePreparationHost{
		projection.Target: {
			Kind: hostfs.EntryRegular,
			Content: []byte(
				`{"mcpServers":{"context7":` + projection.DesiredEntry + `}}`,
			),
		},
		projection.RegistryTarget: {
			Kind: hostfs.EntryRegular,
			Content: []byte(
				`{"version":1,"servers":{"context7":` + projection.DesiredEntry + `}}`,
			),
		},
	}
	genericInspection, err := configuration.Inspect(nil, host)
	if err != nil {
		t.Fatal(err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{projection}, lifecycleMCPCatalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	service, err := NewWithInspections(
		testModel(t),
		domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: domain.ComponentAntigravity2,
			Artifacts: []domain.Artifact{
				artifact(
					domain.RootAntigravityConfig,
					"plugins/mainframe",
					domain.OwnershipManagedExact,
				),
			},
		}}},
		genericInspection,
		mcpInspection,
	)
	if err != nil {
		t.Fatal(err)
	}
	service, err = service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID: domain.ComponentAntigravity2,
		Status:      hostcompatibility.StatusIncompatible,
	}})
	if err != nil {
		t.Fatal(err)
	}
	return service
}
