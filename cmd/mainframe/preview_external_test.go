package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewServiceReadsCodexHookTrustThroughExternalObserver(t *testing.T) {
	service := buildExternalPreviewService(t)
	for _, candidate := range service.Targets() {
		if candidate.ID != domain.ComponentCodex {
			continue
		}
		if len(candidate.Configuration) != 1 ||
			candidate.Configuration[0].Status != lifecycle.ConfigurationReady {
			t.Fatalf("Codex configuration = %#v", candidate.Configuration)
		}
		preview, err := service.Preview([]domain.ComponentID{domain.ComponentCodex})
		if err != nil {
			t.Fatalf("Preview() error = %v", err)
		}
		if len(preview.Configuration.ManualActions) != 0 {
			t.Fatalf("manual actions = %#v", preview.Configuration.ManualActions)
		}
		return
	}
	t.Fatal("Codex target not found")
}

func buildExternalPreviewService(t *testing.T) lifecycle.Service {
	t.Helper()
	releaseRoot := t.TempDir()
	source := filepath.Join(releaseRoot, "bundles/codex/hooks.json")
	if err := os.MkdirAll(filepath.Dir(source), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	raw := `{"hooks":{"Stop":[{"hooks":[` +
		`{"type":"command","command":"true","async":false}]}]}}`
	if err := os.WriteFile(source, []byte(raw), 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	canonicalSource, err := filepath.EvalSymlinks(source)
	if err != nil {
		t.Fatalf("resolve source: %v", err)
	}
	home := t.TempDir()
	codexRoot := filepath.Join(home, ".codex")
	if err := os.MkdirAll(codexRoot, 0o755); err != nil {
		t.Fatalf("mkdir Codex root: %v", err)
	}
	target := filepath.Join(codexRoot, "hooks.json")
	if err := os.Symlink(canonicalSource, target); err != nil {
		t.Fatalf("link hooks: %v", err)
	}
	t.Setenv("HOME", home)
	t.Setenv("CODEX_HOME", codexRoot)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))
	resource := previewExternalResource()
	service, err := buildPreviewServiceFromContext(
		releaseRoot,
		releasecontract.Release{
			ID:        "test-release",
			Model:     previewExternalModel(t),
			Resources: []releasecontract.Resource{resource},
		},
		"/workspace",
		previewExternalClient{target: target},
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	return service
}

func previewExternalModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{{
				Target:     previewExternalResource().Target,
				SourcePath: "bundles/codex/hooks.json",
			}},
		},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	})
	if err != nil {
		t.Fatalf("install model: %v", err)
	}
	return model
}

func previewExternalResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "codex.hook-trust",
		ComponentID: domain.ComponentCodex,
		Strategy:    releasecontract.StrategyManualAction,
		SourcePath:  "bundles/codex/hooks.json",
		Target: domain.Location{
			Root: domain.RootCodexConfig,
			Path: "hooks.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		ExternalState: &releasecontract.ExternalStateDescriptor{
			Kind: releasecontract.ExternalStateCodexHookTrust,
		},
	}
}

type previewExternalClient struct {
	target string
}

func (client previewExternalClient) ListHooks(
	context.Context,
	string,
) (codexstate.Listing, error) {
	return codexstate.Listing{Hooks: []codexstate.Hook{{
		SourcePath:  client.target,
		EventName:   "stop",
		HandlerType: "command",
		Command:     "true",
		Enabled:     true,
		TrustStatus: codexstate.TrustTrusted,
	}}}, nil
}
