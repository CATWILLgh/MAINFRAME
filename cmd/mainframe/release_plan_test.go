package main

import (
	"bytes"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPlanUsesReleaseOnlyComponentAndArtifact(t *testing.T) {
	fixture := usePlanRelease(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{"mainframe-cli"}},
	}

	got := runPlanRequest(t, request)
	want := []domain.Operation{{
		ComponentID: "mainframe-cli",
		Kind:        domain.OperationInstall,
		Artifact: domain.Artifact{Location: domain.Location{
			Root: domain.RootUserBin,
			Path: "mainframe",
		}},
		SourcePath: "bundles/mainframe-cli/mainframe",
	}}
	if !reflect.DeepEqual(got.Operations, want) {
		t.Fatalf("operations = %#v, want %#v; release = %q", got.Operations, want, fixture.root)
	}
}

func TestPlanUsesReleaseDependencyClosure(t *testing.T) {
	usePlanRelease(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{domain.ComponentClaudeCode}},
	}

	got := runPlanRequest(t, request)
	want := []domain.ComponentID{
		domain.ComponentClaudeCode,
		"credential-tools",
		"mainframe-cli",
	}
	components := make([]domain.ComponentID, len(got.Operations))
	for index, operation := range got.Operations {
		components[index] = operation.ComponentID
	}
	if !reflect.DeepEqual(components, want) {
		t.Fatalf("operation components = %v, want %v", components, want)
	}
}

func TestPlanFailureLeavesStdoutEmptyForMissingOrTamperedRelease(t *testing.T) {
	for _, test := range []struct {
		name string
		root func(*testing.T) string
	}{
		{
			name: "missing",
			root: func(t *testing.T) string {
				return t.TempDir() + "/missing"
			},
		},
		{
			name: "tampered",
			root: func(t *testing.T) string {
				fixture := writePlanReleaseFixture(t)
				if err := os.WriteFile(fixture.payloads[domain.ComponentCodex], []byte("tampered\n"), 0o644); err != nil {
					t.Fatalf("tamper release: %v", err)
				}
				return fixture.root
			},
		},
	} {
		t.Run(test.name, func(t *testing.T) {
			t.Setenv(releaseRootEnvironment, test.root(t))
			var stdout, stderr bytes.Buffer
			exitCode := run(
				[]string{"plan"},
				strings.NewReader(`{"desired":{"components":[]},"observed":{"components":[]}}`),
				&stdout,
				&stderr,
			)
			if exitCode == 0 || stderr.Len() == 0 {
				t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
			}
			if stdout.Len() != 0 {
				t.Fatalf("stdout = %q, want empty", stdout.String())
			}
		})
	}
}

func TestPlanReloadsAndRevalidatesReleaseForEveryRequest(t *testing.T) {
	fixture := usePlanRelease(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{domain.ComponentCodex}},
	}
	runPlanRequest(t, request)
	if err := os.WriteFile(fixture.payloads[domain.ComponentCodex], []byte("tampered\n"), 0o644); err != nil {
		t.Fatalf("tamper release: %v", err)
	}
	payload, err := json.Marshal(request)
	if err != nil {
		t.Fatalf("encode request: %v", err)
	}
	var stdout, stderr bytes.Buffer
	if exitCode := run([]string{"plan"}, bytes.NewReader(payload), &stdout, &stderr); exitCode == 0 {
		t.Fatalf("tampered release accepted; stdout = %q", stdout.String())
	}
	if stdout.Len() != 0 || !strings.Contains(stderr.String(), "load release") {
		t.Fatalf("stdout = %q, stderr = %q", stdout.String(), stderr.String())
	}
}

func TestPlanFilesystemOperationsMatchLifecyclePreview(t *testing.T) {
	fixture := usePlanRelease(t)
	request := domain.PlanRequest{
		Desired: domain.DesiredState{Components: []domain.ComponentID{domain.ComponentCodex}},
		Observed: domain.ObservedState{Components: []domain.ObservedComponent{{
			ID: domain.ComponentOpenCode,
			Artifacts: []domain.Artifact{{
				Location:  domain.Location{Root: domain.RootOpenCodeConfig, Path: "AGENTS.md"},
				UnitID:    "opencode.artifact",
				Ownership: domain.OwnershipManagedExact,
			}},
		}}},
	}
	cliPlan := runPlanRequest(t, request)
	release, err := releasecontract.Load(fixture.root)
	if err != nil {
		t.Fatalf("load release: %v", err)
	}
	service, err := lifecycle.New(release.Model, request.Observed)
	if err != nil {
		t.Fatalf("build lifecycle preview: %v", err)
	}
	preview, err := service.Preview(lifecycle.PreviewRequest{Components: request.Desired.Components})
	if err != nil {
		t.Fatalf("lifecycle preview: %v", err)
	}
	if !reflect.DeepEqual(publicPlanResponse(cliPlan), publicPlanResponse(preview.Filesystem)) {
		t.Fatalf("CLI operations = %#v, lifecycle operations = %#v", cliPlan.Operations, preview.Filesystem.Operations)
	}
}

func runPlanRequest(t *testing.T, request domain.PlanRequest) domain.Plan {
	t.Helper()
	payload, err := json.Marshal(request)
	if err != nil {
		t.Fatalf("encode request: %v", err)
	}
	var stdout, stderr bytes.Buffer
	if exitCode := run([]string{"plan"}, bytes.NewReader(payload), &stdout, &stderr); exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var result domain.Plan
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatalf("decode plan: %v", err)
	}
	return result
}
