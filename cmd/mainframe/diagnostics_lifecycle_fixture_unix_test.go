//go:build darwin || linux

package main

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type isolatedDiagnosticsLifecycle struct {
	layout      hostlayout.Layout
	model       installmodel.Model
	resource    releasecontract.Resource
	state       *executor.UnixState
	workspace   linkworkspace.Workspace
	baseTarget  string
	devTarget   string
	diagnostics string
	history     string
}

type isolatedDiagnosticsPaths struct {
	baseSource  string
	devSource   string
	baseTarget  string
	devTarget   string
	diagnostics string
	history     string
}

func newIsolatedDiagnosticsLifecycle(
	t *testing.T,
) isolatedDiagnosticsLifecycle {
	t.Helper()
	root := canonicalTempDir(t)
	home := filepath.Join(root, "home")
	source := filepath.Join(root, "release")
	prepareIsolatedDiagnosticsSource(t, home, source)
	layout, err := hostlayout.Resolve(
		hostlayout.Environment{
			LookupEnv:   func(string) (string, bool) { return "", false },
			UserHomeDir: func() (string, error) { return home, nil },
			GOOS:        runtime.GOOS,
		},
		source,
	)
	if err != nil {
		t.Fatalf("hostlayout.Resolve() error = %v", err)
	}
	paths := prepareIsolatedDiagnosticsTargets(t, home, source)
	state := openIsolatedDiagnosticsState(t, layout, paths)
	workspace, err := linkworkspace.New(source, layout.Targets())
	if err != nil {
		state.Close()
		t.Fatalf("linkworkspace.New() error = %v", err)
	}
	return isolatedDiagnosticsLifecycle{
		layout: layout, model: isolatedDiagnosticsModel(t),
		resource: isolatedDiagnosticsResource(),
		state:    state, workspace: workspace,
		baseTarget: paths.baseTarget, devTarget: paths.devTarget,
		diagnostics: paths.diagnostics, history: paths.history,
	}
}

func prepareIsolatedDiagnosticsSource(
	t *testing.T,
	home string,
	source string,
) {
	t.Helper()
	if err := os.MkdirAll(home, 0o700); err != nil {
		t.Fatal(err)
	}
	baseParent := filepath.Join(source, "bundles", "claude-code")
	if err := os.MkdirAll(baseParent, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(baseParent, "base"),
		[]byte("base"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(
		filepath.Join(source, "dev", "harness-feedback-plugin"),
		0o755,
	); err != nil {
		t.Fatal(err)
	}
}

func prepareIsolatedDiagnosticsTargets(
	t *testing.T,
	home string,
	source string,
) isolatedDiagnosticsPaths {
	t.Helper()
	paths := isolatedDiagnosticsPaths{
		baseSource: filepath.Join(source, "bundles", "claude-code", "base"),
		devSource:  filepath.Join(source, "dev", "harness-feedback-plugin"),
		baseTarget: filepath.Join(home, ".claude", "mainframe", "base"),
		devTarget:  filepath.Join(home, ".claude", "skills", "mainframe-dev"),
		diagnostics: filepath.Join(
			home, ".claude", "mainframe", "diagnostics.json",
		),
		history: filepath.Join(
			home, ".claude", "mainframe", "telemetry", "events.db",
		),
	}
	for _, directory := range []string{
		filepath.Dir(paths.baseTarget),
		filepath.Dir(paths.devTarget),
		filepath.Dir(paths.history),
	} {
		if err := os.MkdirAll(directory, 0o700); err != nil {
			t.Fatal(err)
		}
	}
	for target, sourcePath := range map[string]string{
		paths.baseTarget: paths.baseSource,
		paths.devTarget:  paths.devSource,
	} {
		if err := os.Symlink(sourcePath, target); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(
		paths.diagnostics,
		[]byte(`{"events":true,"feedback":true,"schema_version":1}`),
		0o600,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(paths.history, []byte("history"), 0o600); err != nil {
		t.Fatal(err)
	}
	return paths
}

func openIsolatedDiagnosticsState(
	t *testing.T,
	layout hostlayout.Layout,
	paths isolatedDiagnosticsPaths,
) *executor.UnixState {
	t.Helper()
	state, err := executor.OpenUnixState(layout.State())
	if err != nil {
		t.Fatalf("executor.OpenUnixState() error = %v", err)
	}
	registry, err := linkownership.New([]linkownership.Claim{
		isolatedDiagnosticsClaim(
			"claude-code.base", "mainframe/base", paths.baseSource,
		),
		isolatedDiagnosticsClaim(
			"claude-code.dev.harness-feedback",
			"skills/mainframe-dev",
			paths.devSource,
		),
	})
	if err != nil {
		state.Close()
		t.Fatalf("linkownership.New() error = %v", err)
	}
	if err := state.SaveOwnership(registry); err != nil {
		state.Close()
		t.Fatalf("SaveOwnership() error = %v", err)
	}
	return state
}

func isolatedDiagnosticsModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				{
					UnitID: "claude-code.base",
					Target: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "mainframe/base",
					},
					SourcePath: "bundles/claude-code/base",
				},
				{
					UnitID: "claude-code.dev.harness-feedback",
					Target: domain.Location{
						Root: domain.RootClaudeConfig,
						Path: "skills/mainframe-dev",
					},
					SourcePath: "dev/harness-feedback-plugin",
					Feature:    domain.FeatureHarnessFeedback,
				},
			},
		},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	return model
}

func isolatedDiagnosticsResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "claude-code.diagnostics",
		ComponentID: domain.ComponentClaudeCode,
		Strategy:    releasecontract.StrategyExactJSONDocument,
		SourcePath:  "bundles/claude-code/diagnostics.json",
		Target: domain.Location{
			Root: domain.RootClaudeConfig,
			Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
}

func isolatedDiagnosticsClaim(
	unitID string,
	target domain.ArtifactPath,
	rawTarget string,
) linkownership.Claim {
	return linkownership.Claim{
		UnitID:      unitID,
		ComponentID: domain.ComponentClaudeCode,
		Target: domain.Location{
			Root: domain.RootClaudeConfig,
			Path: target,
		},
		RawTarget:   rawTarget,
		ReleaseID:   "release",
		IndexSHA256: diagnosticsLifecycleDigest,
	}
}
