//go:build darwin || linux

package main

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const diagnosticsLifecycleDigest = "abababababababababababababababababababababababababababababababab"

func TestIsolatedDiagnosticsLifecycleUninstallsAndReenablesDEV(t *testing.T) {
	fixture := newIsolatedDiagnosticsLifecycle(t)
	defer fixture.state.Close()

	uninstall := fixture.preview(t, lifecycle.PreviewRequest{})
	if len(uninstall.Plan.Operations) != 2 ||
		len(uninstall.Configuration.Transitions()) != 1 {
		t.Fatalf("uninstall preview = %#v", uninstall)
	}
	fixture.apply(t, uninstall)
	fixture.assertRemoved(t)

	reenable := fixture.preview(t, lifecycle.PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentClaudeCode},
		Diagnostics: diagnostics.Desired{
			Configured: true,
			Events:     true,
			Feedback:   true,
		},
	})
	if len(reenable.Plan.Operations) != 2 ||
		len(reenable.Configuration.Transitions()) != 1 {
		t.Fatalf("re-enable preview = %#v", reenable)
	}
	fixture.apply(t, reenable)
	fixture.assertReenabled(t)
}

func (fixture isolatedDiagnosticsLifecycle) preview(
	t *testing.T,
	request lifecycle.PreviewRequest,
) executor.Preview {
	t.Helper()
	namespace, err := hostfs.Open(fixture.layout)
	if err != nil {
		t.Fatalf("hostfs.Open() error = %v", err)
	}
	registry, err := fixture.state.LoadOwnership()
	if err != nil {
		t.Fatalf("LoadOwnership() error = %v", err)
	}
	observed, err := discovery.DiscoverWithOwnership(
		fixture.model,
		namespace.Filesystem(),
		namespace.Roots(),
		registry,
	)
	if err != nil {
		t.Fatalf("DiscoverWithOwnership() error = %v", err)
	}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{fixture.resource},
		namespace,
	)
	if err != nil {
		t.Fatalf("configuration.Inspect() error = %v", err)
	}
	service, err := lifecycle.NewWithInspection(
		fixture.model,
		observed,
		inspection,
	)
	if err != nil {
		t.Fatalf("lifecycle.NewWithInspection() error = %v", err)
	}
	semantic, err := service.Preview(request)
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	prepared, err := service.PrepareConfiguration(request)
	if err != nil {
		t.Fatalf("PrepareConfiguration() error = %v", err)
	}
	return executor.Preview{
		Release: executor.ReleaseIdentity{
			ID:          "release",
			IndexSHA256: diagnosticsLifecycleDigest,
		},
		Desired:       append([]domain.ComponentID(nil), request.Components...),
		Plan:          semantic.Filesystem,
		Configuration: prepared,
	}
}

func (fixture isolatedDiagnosticsLifecycle) apply(
	t *testing.T,
	preview executor.Preview,
) {
	t.Helper()
	runner := executor.NewWithConfiguration(
		fixture.state,
		fixture.state,
		fixedPreviewRefresher{preview: preview},
		fixture.workspace,
		fixture.workspace,
	)
	if _, err := runner.Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
}

func (fixture isolatedDiagnosticsLifecycle) assertRemoved(t *testing.T) {
	t.Helper()
	for _, target := range []string{
		fixture.baseTarget,
		fixture.devTarget,
		fixture.diagnostics,
	} {
		if _, err := os.Lstat(target); !os.IsNotExist(err) {
			t.Fatalf("managed target remains at %q: %v", target, err)
		}
	}
	if content, err := os.ReadFile(fixture.history); err != nil ||
		string(content) != "history" {
		t.Fatalf("diagnostic history = %q, %v", content, err)
	}
	registry, err := fixture.state.LoadOwnership()
	if err != nil || len(registry.Claims()) != 0 {
		t.Fatalf("ownership after uninstall = %#v, %v", registry.Claims(), err)
	}
}

func (fixture isolatedDiagnosticsLifecycle) assertReenabled(t *testing.T) {
	t.Helper()
	for _, target := range []string{fixture.baseTarget, fixture.devTarget} {
		info, err := os.Lstat(target)
		if err != nil || info.Mode()&os.ModeSymlink == 0 {
			t.Fatalf("managed link at %q = %v, %v", target, info, err)
		}
	}
	content, err := os.ReadFile(fixture.diagnostics)
	if err != nil ||
		!strings.Contains(string(content), `"events": true`) ||
		!strings.Contains(string(content), `"feedback": true`) {
		t.Fatalf("diagnostics activation = %q, %v", content, err)
	}
	if history, err := os.ReadFile(fixture.history); err != nil ||
		string(history) != "history" {
		t.Fatalf("diagnostic history = %q, %v", history, err)
	}
	registry, err := fixture.state.LoadOwnership()
	if err != nil || len(registry.Claims()) != 2 {
		t.Fatalf("ownership after re-enable = %#v, %v", registry.Claims(), err)
	}
}

type fixedPreviewRefresher struct {
	preview executor.Preview
}

func (refresher fixedPreviewRefresher) Refresh(
	[]domain.ComponentID,
) (executor.Preview, error) {
	return refresher.preview, nil
}
