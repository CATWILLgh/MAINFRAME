package lifecycle

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

func TestPreviewTargetsReportManagedAttentionAndAbsent(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []domain.Artifact{
				artifact(domain.RootClaudeConfig, "CLAUDE.md", domain.OwnershipManagedExact),
			},
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []domain.Artifact{
				artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipConflict),
			},
		},
	}})

	want := []Target{
		{ID: domain.ComponentClaudeCode, Status: StatusManaged, Selected: true},
		{ID: domain.ComponentCodex, Status: StatusAttention, Selected: true},
		{ID: domain.ComponentOpenCode, Status: StatusAbsent},
	}
	if got := service.Targets(); !reflect.DeepEqual(got, want) {
		t.Fatalf("targets = %#v, want %#v", got, want)
	}
}

func TestPreviewBuildsPlanForVisibleTargets(t *testing.T) {
	service := newTestService(t, domain.ObservedState{Components: []domain.ObservedComponent{
		{
			ID: domain.ComponentCodex,
			Artifacts: []domain.Artifact{
				artifact(domain.RootCodexConfig, "AGENTS.md", domain.OwnershipManagedExact),
			},
		},
	}})

	result, err := service.Plan([]domain.ComponentID{
		domain.ComponentClaudeCode,
		domain.ComponentOpenCode,
	})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	wantKinds := map[domain.ComponentID]domain.OperationKind{
		domain.ComponentClaudeCode: domain.OperationInstall,
		domain.ComponentCodex:      domain.OperationRemove,
		domain.ComponentOpenCode:   domain.OperationInstall,
	}
	if len(result.Operations) != len(wantKinds) {
		t.Fatalf("operations = %#v", result.Operations)
	}
	for _, operation := range result.Operations {
		if wantKinds[operation.ComponentID] != operation.Kind {
			t.Fatalf("operation = %#v, want kind %q", operation, wantKinds[operation.ComponentID])
		}
	}
}

func TestPreviewRejectsInternalAndDuplicateSelections(t *testing.T) {
	service := newTestService(t, domain.ObservedState{})
	tests := []struct {
		name       string
		components []domain.ComponentID
		message    string
	}{
		{
			name:       "internal component",
			components: []domain.ComponentID{domain.ComponentCodexGates},
			message:    "not selectable",
		},
		{
			name: "duplicate component",
			components: []domain.ComponentID{
				domain.ComponentCodex,
				domain.ComponentCodex,
			},
			message: "duplicate",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := service.Plan(test.components)
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("error = %v, want containing %q", err, test.message)
			}
		})
	}
}

func newTestService(t *testing.T, observed domain.ObservedState) Service {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootClaudeConfig, "CLAUDE.md", "claude/CLAUDE.md"),
			},
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootCodexConfig, "AGENTS.md", "codex/AGENTS.md"),
			},
		},
		{
			ID: domain.ComponentOpenCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootOpenCodeConfig, "AGENTS.md", "opencode/AGENTS.md"),
			},
		},
		{ID: domain.ComponentCodexGates},
	})
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	service, err := New(model, observed)
	if err != nil {
		t.Fatalf("service: %v", err)
	}
	return service
}

func desired(root domain.RootID, target, source domain.ArtifactPath) installmodel.ArtifactSpec {
	return installmodel.ArtifactSpec{
		Target:     domain.Location{Root: root, Path: target},
		SourcePath: source,
	}
}

func artifact(root domain.RootID, path domain.ArtifactPath, ownership domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{
		Location:  domain.Location{Root: root, Path: path},
		Ownership: ownership,
	}
}
