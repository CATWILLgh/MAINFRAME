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
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
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
			preview, err := service.Preview(lifecycle.PreviewRequest{})
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

func TestBuildPreviewServicePlansSelectedOpenCodeMCP(t *testing.T) {
	home := t.TempDir()
	configRoot := filepath.Join(home, ".config")
	openCodeRoot := filepath.Join(configRoot, "opencode")
	if err := os.MkdirAll(openCodeRoot, 0o700); err != nil {
		t.Fatalf("mkdir OpenCode root: %v", err)
	}
	writePreviewFile(t, filepath.Join(openCodeRoot, "opencode.json"), `{}`)
	t.Setenv("HOME", home)
	t.Setenv("XDG_CONFIG_HOME", configRoot)
	catalogPayload, err := os.ReadFile("../../internal/mcpcatalog/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := mcpcatalog.Parse(catalogPayload)
	if err != nil {
		t.Fatal(err)
	}
	service, err := buildPreviewServiceFrom(
		t.TempDir(),
		releasecontract.Release{
			ID:             "test-release",
			Model:          previewOwnershipModel(t),
			Resources:      []releasecontract.Resource{previewOwnershipResource()},
			MCPCatalog:     catalog,
			MCPProjections: []releasecontract.MCPProjection{previewMCPProjection()},
		},
	)
	if err != nil {
		t.Fatalf("build preview service: %v", err)
	}
	preview, err := service.Preview(lifecycle.PreviewRequest{
		Components: []domain.ComponentID{domain.ComponentOpenCode},
		MCPSelections: []mcpcatalog.Selection{{
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		}},
	})
	if err != nil {
		t.Fatalf("preview selected MCP: %v", err)
	}
	if preview.MCP.Blocking || len(preview.MCP.Intents) != 1 ||
		preview.MCP.Intents[0].Kind != mcpconfiguration.IntentAdd {
		t.Fatalf("MCP preview = %#v", preview.MCP)
	}
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

func previewMCPProjection() releasecontract.MCPProjection {
	return releasecontract.MCPProjection{
		ID:          "opencode.mcp.context7",
		ComponentID: domain.ComponentOpenCode,
		Codec:       releasecontract.MCPProjectionOpenCodeRemote,
		ServerID:    "context7",
		ProfileID:   "remote-keyless",
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json",
		},
		MapPointer: "/mcp",
		EntryKey:   "context7",
		RegistryTarget: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json.mainframe-mcp.json",
		},
		RegistrySchemaVersion:  1,
		RegistryEntriesPointer: "/servers",
		DesiredEntry:           `{"type":"remote","url":"https://mcp.context7.com/mcp"}`,
	}
}
