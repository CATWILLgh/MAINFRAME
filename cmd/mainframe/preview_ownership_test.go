package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewServiceObservesOpenCodePermissionOwnership(t *testing.T) {
	home := t.TempDir()
	configRoot := filepath.Join(home, ".config")
	openCodeRoot := filepath.Join(configRoot, "opencode")
	if err := os.MkdirAll(openCodeRoot, 0o700); err != nil {
		t.Fatalf("mkdir OpenCode root: %v", err)
	}
	writePreviewFile(
		t,
		filepath.Join(openCodeRoot, "opencode.json"),
		`{"permission":{"bash":{"*":"allow"}}}`,
	)
	writePreviewFile(
		t,
		filepath.Join(openCodeRoot, "opencode.json.mainframe-permissions.json"),
		`{"version":1,"actions":{"bash":{"*":"allow"}}}`,
	)
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", configRoot)
	model := previewOwnershipModel(t)
	service, err := buildPreviewServiceFrom(
		t.TempDir(),
		releasecontract.Release{
			ID:        "test-release",
			Model:     model,
			Resources: []releasecontract.Resource{previewOwnershipResource()},
		},
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	for _, target := range service.Targets() {
		if target.ID == domain.ComponentOpenCode {
			if len(target.Configuration) != 1 ||
				target.Configuration[0].Status != lifecycle.ConfigurationReady {
				t.Fatalf("OpenCode configuration = %#v", target.Configuration)
			}
			preview, err := service.Preview(nil)
			if err != nil {
				t.Fatalf("preview deselection: %v", err)
			}
			want := configuration.Change{
				ResourceID:  "opencode.permissions",
				ComponentID: domain.ComponentOpenCode,
				UnitID:      "bash",
				Kind:        configuration.ChangeRemove,
			}
			if !reflect.DeepEqual(preview.Configuration.Changes, []configuration.Change{want}) {
				t.Fatalf("configuration changes = %#v, want %#v", preview.Configuration.Changes, want)
			}
			return
		}
	}
	t.Fatal("OpenCode target not found")
}

func writePreviewFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func previewOwnershipModel(t *testing.T) installmodel.Model {
	t.Helper()
	specs := []installmodel.ComponentSpec{
		{ID: domain.ComponentClaudeCode},
		{ID: domain.ComponentCodex},
		{ID: domain.ComponentOpenCode},
		{ID: domain.ComponentAntigravity2},
	}
	model, err := installmodel.New(specs)
	if err != nil {
		t.Fatalf("model: %v", err)
	}
	return model
}

func previewOwnershipResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "opencode.permissions",
		ComponentID: domain.ComponentOpenCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer:  "/permission",
			EntrySchema: "decision-rule-v1",
			DesiredMap:  `{"bash":{"*":"allow"}}`,
			RegistryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-permissions.json",
			},
			RegistrySchemaVersion: 1,
			EntriesPointer:        "/actions",
		},
	}
}
