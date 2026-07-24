package lifecycle

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPreviewRemovesDiagnosticsOnlyForDeselectedInstalledAdapter(t *testing.T) {
	claude := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	codex := lifecycleDiagnosticsResource(domain.ComponentCodex)
	claudeEntry := lifecycleDiagnosticsEntry([]byte(
		`{"events":true,"feedback":true,"schema_version":1}`,
	))
	codexEntry := lifecycleDiagnosticsEntry([]byte(
		`{"events":true,"feedback":false,"schema_version":1}`,
	))
	codexEntry.Inode++
	service := lifecycleDiagnosticsServiceWithObserved(
		t,
		[]releasecontract.Resource{claude, codex},
		lifecyclePreparationHost{
			claude.Target: claudeEntry,
			codex.Target:  codexEntry,
		},
		diagnosticsObservedState(domain.ComponentClaudeCode, domain.ComponentCodex),
	)

	preview, err := service.Preview(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentCodex},
	})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if !preview.Diagnostics.Executable ||
		len(preview.Diagnostics.Intents) != 1 ||
		preview.Diagnostics.Intents[0].ComponentID != domain.ComponentClaudeCode {
		t.Fatalf("diagnostics plan = %#v", preview.Diagnostics)
	}
	if len(preview.Configuration.Changes) != 1 ||
		preview.Configuration.Changes[0].ResourceID != claude.ID ||
		preview.Configuration.Changes[0].Kind != configuration.ChangeRemove {
		t.Fatalf("configuration plan = %#v", preview.Configuration)
	}

	prepared, err := service.PrepareConfiguration(PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentCodex},
	})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 ||
		transitions[0].ResourceIDs[0] != claude.ID ||
		transitions[0].Mutations[0].After.Exists {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
}

func TestPreviewCompleteUninstallRemovesEveryInstalledDiagnosticsDocument(t *testing.T) {
	claude := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	codex := lifecycleDiagnosticsResource(domain.ComponentCodex)
	claudeEntry := lifecycleDiagnosticsEntry([]byte(
		`{"events":true,"feedback":true,"schema_version":1}`,
	))
	codexEntry := lifecycleDiagnosticsEntry([]byte(
		`{"events":true,"feedback":false,"schema_version":1}`,
	))
	codexEntry.Inode++
	service := lifecycleDiagnosticsServiceWithObserved(
		t,
		[]releasecontract.Resource{claude, codex},
		lifecyclePreparationHost{
			claude.Target: claudeEntry,
			codex.Target:  codexEntry,
		},
		diagnosticsObservedState(domain.ComponentClaudeCode, domain.ComponentCodex),
	)

	prepared, err := service.PrepareConfiguration(PreviewRequest{})
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 2 {
		t.Fatalf("prepared transitions = %#v", transitions)
	}
	for _, transition := range transitions {
		if transition.Mutations[0].After.Exists {
			t.Fatalf("transition retained activation document = %#v", transition)
		}
	}
}

func TestPreviewPreservesDiagnosticsForIncompatibleInstalledAdapter(t *testing.T) {
	antigravity := lifecycleDiagnosticsResource(domain.ComponentAntigravity2)
	service := lifecycleDiagnosticsServiceWithObserved(
		t,
		[]releasecontract.Resource{antigravity},
		lifecyclePreparationHost{
			antigravity.Target: lifecycleDiagnosticsEntry([]byte(
				`{"events":true,"feedback":false,"schema_version":1}`,
			)),
		},
		diagnosticsObservedState(domain.ComponentAntigravity2),
	)
	service, err := service.WithHostCompatibility([]hostcompatibility.Assessment{{
		ComponentID: domain.ComponentAntigravity2,
		Status:      hostcompatibility.StatusIncompatible,
	}})
	if err != nil {
		t.Fatalf("WithHostCompatibility() error = %v", err)
	}

	preview, err := service.Preview(PreviewRequest{})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.Diagnostics.Intents) != 0 ||
		len(preview.Configuration.Changes) != 0 {
		t.Fatalf("preview = %#v", preview)
	}
}

func TestPreviewDoesNotRemoveDiagnosticsForForeignAdapterState(t *testing.T) {
	claude := lifecycleDiagnosticsResource(domain.ComponentClaudeCode)
	foreign := diagnosticsObservedState(domain.ComponentClaudeCode)
	foreign.Components[0].Artifacts[0].UnitID = ""
	foreign.Components[0].Artifacts[0].Ownership = domain.OwnershipForeign
	service := lifecycleDiagnosticsServiceWithObserved(
		t,
		[]releasecontract.Resource{claude},
		lifecyclePreparationHost{
			claude.Target: lifecycleDiagnosticsEntry([]byte(
				`{"events":true,"feedback":false,"schema_version":1}`,
			)),
		},
		foreign,
	)

	preview, err := service.Preview(PreviewRequest{})
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	if len(preview.Diagnostics.Intents) != 0 ||
		len(preview.Configuration.Changes) != 0 {
		t.Fatalf("preview = %#v", preview)
	}
}

func lifecycleDiagnosticsServiceWithObserved(
	t *testing.T,
	resources []releasecontract.Resource,
	host configuration.Host,
	observed domain.ObservedState,
) Service {
	t.Helper()
	inspection, err := configuration.Inspect(resources, host)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	service, err := NewWithInspection(
		diagnosticsLifecycleModel(t),
		observed,
		inspection,
	)
	if err != nil {
		t.Fatalf("NewWithInspection() error = %v", err)
	}
	return service
}

func diagnosticsLifecycleModel(t *testing.T) installmodel.Model {
	t.Helper()
	components := make([]installmodel.ComponentSpec, 0, len(visibleTargets))
	for _, component := range visibleTargets {
		components = append(components, installmodel.ComponentSpec{
			ID: component,
			Artifacts: []installmodel.ArtifactSpec{{
				UnitID: string(component) + ".base",
				Target: domain.Location{
					Root: diagnosticsRoot(component),
					Path: "mainframe/base",
				},
				SourcePath: "bundles/" + domain.ArtifactPath(component) + "/base",
			}},
		})
	}
	model, err := installmodel.New(components)
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	return model
}

func diagnosticsObservedState(
	components ...domain.ComponentID,
) domain.ObservedState {
	observed := domain.ObservedState{}
	for _, component := range components {
		observed.Components = append(observed.Components, domain.ObservedComponent{
			ID: component,
			Artifacts: []domain.Artifact{{
				Location: domain.Location{
					Root: diagnosticsRoot(component),
					Path: "mainframe/base",
				},
				UnitID:    string(component) + ".base",
				Ownership: domain.OwnershipManagedExact,
			}},
		})
	}
	return observed
}

func diagnosticsRoot(component domain.ComponentID) domain.RootID {
	switch component {
	case domain.ComponentClaudeCode:
		return domain.RootClaudeConfig
	case domain.ComponentCodex:
		return domain.RootCodexConfig
	case domain.ComponentOpenCode:
		return domain.RootOpenCodeConfig
	default:
		return domain.RootAntigravityData
	}
}
