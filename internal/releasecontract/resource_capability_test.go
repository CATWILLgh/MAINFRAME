package releasecontract_test

import (
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestAdapterSeededFileWithManagedRegistrySupportsApply(t *testing.T) {
	components := map[domain.ComponentID]domain.RootID{
		domain.ComponentClaudeCode:   domain.RootClaudeConfig,
		domain.ComponentCodex:        domain.RootCodexConfig,
		domain.ComponentOpenCode:     domain.RootOpenCodeConfig,
		domain.ComponentAntigravity2: domain.RootAntigravityData,
	}
	for component, root := range components {
		t.Run(string(component), func(t *testing.T) {
			resource := releasecontract.Resource{
				ID:            string(component) + ".credentials-index",
				ComponentID:   component,
				Strategy:      releasecontract.StrategySeedIfAbsent,
				Apply:         releasecontract.SupportSupported,
				Observation:   releasecontract.SupportSupported,
				SourcePath:    "credentials-index.md",
				SourceContent: []byte("index"),
				Target: domain.Location{
					Root: root, Path: "credentials-index.md",
				},
				FileOwnership: &releasecontract.FileOwnership{
					RegistryTarget: domain.Location{
						Root: root, Path: "mainframe/file-ownership.json",
					},
					RegistrySchemaVersion: 1,
				},
			}

			if !resource.SupportsApply() {
				t.Fatal("SupportsApply() = false, want true")
			}
			if !resource.SupportsPreparation() {
				t.Fatal("SupportsPreparation() = false, want true")
			}
		})
	}
}

func TestAdapterJSONClaimsSupportApplyInItsOwnRoot(t *testing.T) {
	resource := releasecontract.Resource{
		ID:          "claude-code.settings",
		ComponentID: domain.ComponentClaudeCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Apply:       releasecontract.SupportSupported,
		Observation: releasecontract.SupportSupported,
		Target: domain.Location{
			Root: domain.RootClaudeConfig, Path: "settings.json",
		},
		JSONClaimOwnership: &releasecontract.JSONClaimOwnership{
			RegistryTarget: domain.Location{
				Root: domain.RootClaudeConfig,
				Path: "mainframe/config-ownership.json",
			},
			RegistrySchemaVersion: 1,
			Claims: []releasecontract.JSONClaim{{
				ID:            "permission-allow-0",
				Kind:          releasecontract.JSONClaimArrayEntry,
				Pointer:       "/permissions/allow",
				SelectorValue: `"Bash(ls:*)"`,
			}},
		},
	}

	if !resource.SupportsApply() {
		t.Fatal("SupportsApply() = false, want true")
	}
}

func TestAdapterJSONClaimsRejectARegistryOutsideItsOwnRoot(t *testing.T) {
	resource := releasecontract.Resource{
		ID:          "claude-code.settings",
		ComponentID: domain.ComponentClaudeCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Apply:       releasecontract.SupportSupported,
		Observation: releasecontract.SupportSupported,
		Target: domain.Location{
			Root: domain.RootClaudeConfig, Path: "settings.json",
		},
		JSONClaimOwnership: &releasecontract.JSONClaimOwnership{
			RegistryTarget: domain.Location{
				Root: domain.RootCodexConfig,
				Path: "mainframe/config-ownership.json",
			},
			RegistrySchemaVersion: 1,
			Claims: []releasecontract.JSONClaim{{
				ID: "permission-allow-0", Kind: releasecontract.JSONClaimArrayEntry,
				Pointer: "/permissions/allow", SelectorValue: `"Bash(ls:*)"`,
			}},
		},
	}

	if resource.SupportsApply() {
		t.Fatal("SupportsApply() = true for a registry in a foreign root")
	}
}

func TestAdapterSeededFileRejectsARegistryOutsideItsOwnRoot(t *testing.T) {
	resource := releasecontract.Resource{
		ID:            "codex.credentials-index",
		ComponentID:   domain.ComponentCodex,
		Strategy:      releasecontract.StrategySeedIfAbsent,
		Apply:         releasecontract.SupportSupported,
		Observation:   releasecontract.SupportSupported,
		SourcePath:    "credentials-index.md",
		SourceContent: []byte("index"),
		Target: domain.Location{
			Root: domain.RootCodexConfig, Path: "credentials-index.md",
		},
		FileOwnership: &releasecontract.FileOwnership{
			RegistryTarget: domain.Location{
				Root: domain.RootClaudeConfig,
				Path: "mainframe/file-ownership.json",
			},
			RegistrySchemaVersion: 1,
		},
	}

	if resource.SupportsApply() {
		t.Fatal("SupportsApply() = true for a registry in a foreign root")
	}
}

func TestResourceApplyCapabilityPredicateMatrix(t *testing.T) {
	tests := map[string]struct {
		mutate func(*releasecontract.Resource)
		want   bool
	}{
		"supported":         {mutate: func(*releasecontract.Resource) {}, want: true},
		"unsupported apply": {mutate: func(item *releasecontract.Resource) { item.Apply = "future" }},
		"wrong component":   {mutate: func(item *releasecontract.Resource) { item.ComponentID = domain.ComponentCodex }},
		"wrong strategy":    {mutate: func(item *releasecontract.Resource) { item.Strategy = releasecontract.StrategySeedIfAbsent }},
		"wrong observation": {mutate: func(item *releasecontract.Resource) { item.Observation = releasecontract.SupportUnimplemented }},
		"wrong target root": {mutate: func(item *releasecontract.Resource) { item.Target.Root = domain.RootCodexConfig }},
		"static ownership": {mutate: func(item *releasecontract.Resource) {
			item.OwnedJSONFields = []releasecontract.JSONField{{Pointer: "/permission"}}
		}},
		"missing ownership":  {mutate: func(item *releasecontract.Resource) { item.JSONMapOwnership = nil }},
		"wrong entry schema": {mutate: func(item *releasecontract.Resource) { item.JSONMapOwnership.EntrySchema = "future" }},
		"wrong registry root": {mutate: func(item *releasecontract.Resource) {
			item.JSONMapOwnership.RegistryTarget.Root = domain.RootCodexConfig
		}},
		"wrong registry version": {mutate: func(item *releasecontract.Resource) { item.JSONMapOwnership.RegistrySchemaVersion = 2 }},
		"wrong entries pointer":  {mutate: func(item *releasecontract.Resource) { item.JSONMapOwnership.EntriesPointer = "/servers" }},
		"external state":         {mutate: func(item *releasecontract.Resource) { item.ExternalState = &releasecontract.ExternalStateDescriptor{} }},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			resource := applySupportedResource()
			test.mutate(&resource)
			if got := resource.SupportsApply(); got != test.want {
				t.Fatalf("SupportsApply() = %t, want %t", got, test.want)
			}
		})
	}
}

func TestLoadPreservesSupportedOpenCodePermissionApply(t *testing.T) {
	root := writeApplySupportedOwnershipFixture(t, "opencode", "opencode-config")
	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("load supported OpenCode ownership: %v", err)
	}
	if release.Resources[0].Apply != releasecontract.SupportSupported {
		t.Fatalf("apply support = %q", release.Resources[0].Apply)
	}
}

func TestLoadRejectsSupportedApplyOutsideOpenCodePermissionOwnership(t *testing.T) {
	root := writeApplySupportedOwnershipFixture(t, "codex", "codex-config")
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("supported apply outside OpenCode permission ownership was accepted")
	}
}

func TestExactJSONDocumentApplyCapabilityIsAdapterLocalAndNarrow(t *testing.T) {
	tests := map[string]struct {
		mutate func(*releasecontract.Resource)
		want   bool
	}{
		"supported": {mutate: func(*releasecontract.Resource) {}, want: true},
		"unsupported apply": {mutate: func(item *releasecontract.Resource) {
			item.Apply = releasecontract.SupportUnimplemented
		}},
		"unsupported observation": {mutate: func(item *releasecontract.Resource) {
			item.Observation = releasecontract.SupportUnimplemented
		}},
		"wrong component": {mutate: func(item *releasecontract.Resource) {
			item.ComponentID = "credential-tools"
		}},
		"wrong root": {mutate: func(item *releasecontract.Resource) {
			item.Target.Root = domain.RootOpenCodeConfig
		}},
		"wrong path": {mutate: func(item *releasecontract.Resource) {
			item.Target.Path = "opencode.json"
		}},
		"missing exemplar": {mutate: func(item *releasecontract.Resource) {
			item.ExactJSONExemplar = ""
		}},
		"invalid exemplar": {mutate: func(item *releasecontract.Resource) {
			item.ExactJSONExemplar = `{"events":false}`
		}},
		"legacy source": {mutate: func(item *releasecontract.Resource) {
			item.LegacySourceSuffixes = []domain.ArtifactPath{"legacy.json"}
		}},
		"JSON fields": {mutate: func(item *releasecontract.Resource) {
			item.OwnedJSONFields = []releasecontract.JSONField{{Pointer: "/events"}}
		}},
		"map ownership": {mutate: func(item *releasecontract.Resource) {
			item.JSONMapOwnership = &releasecontract.JSONMapOwnership{}
		}},
		"external state": {mutate: func(item *releasecontract.Resource) {
			item.ExternalState = &releasecontract.ExternalStateDescriptor{}
		}},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			resource := exactJSONResource()
			test.mutate(&resource)
			if got := resource.SupportsApply(); got != test.want {
				t.Fatalf("SupportsApply() = %t, want %t", got, test.want)
			}
		})
	}
}

func TestExactJSONDocumentUsesEachAdapterRuntimeRoot(t *testing.T) {
	tests := map[string]struct {
		component domain.ComponentID
		root      domain.RootID
		want      bool
	}{
		"Claude config": {
			component: domain.ComponentClaudeCode,
			root:      domain.RootClaudeConfig,
			want:      true,
		},
		"Codex config": {
			component: domain.ComponentCodex,
			root:      domain.RootCodexConfig,
			want:      true,
		},
		"OpenCode config": {
			component: domain.ComponentOpenCode,
			root:      domain.RootOpenCodeConfig,
			want:      true,
		},
		"Antigravity data": {
			component: domain.ComponentAntigravity2,
			root:      domain.RootAntigravityData,
			want:      true,
		},
		"Antigravity plugin config": {
			component: domain.ComponentAntigravity2,
			root:      domain.RootAntigravityConfig,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			resource := exactJSONResource()
			resource.ComponentID = test.component
			resource.Target.Root = test.root
			if got := resource.SupportsApply(); got != test.want {
				t.Fatalf("SupportsApply() = %t, want %t", got, test.want)
			}
		})
	}
}

func TestLoadRequiresFullySupportedExactJSONDocumentLifecycle(t *testing.T) {
	tests := map[string]func(map[string]any){
		"unimplemented apply": func(resource map[string]any) {
			resource["apply"] = "unimplemented"
		},
		"unimplemented observation": func(resource map[string]any) {
			resource["observation"] = "unimplemented"
		},
		"legacy metadata with supported apply": func(resource map[string]any) {
			resource["legacy_source_suffixes"] = []any{}
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeExactJSONFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resource := manifest["resources"].([]any)[0].(map[string]any)
			mutate(resource)
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("incomplete exact JSON lifecycle was accepted")
			}
		})
	}
}

func TestExactJSONDocumentValidatesRuntimeDesiredBytes(t *testing.T) {
	resource := exactJSONResource()
	canonical, err := resource.ValidateExactJSONDocument(
		[]byte(`{"feedback":true,"schema_version":1,"events":false}`),
	)
	if err != nil {
		t.Fatalf("ValidateExactJSONDocument() error = %v", err)
	}
	if canonical != `{"events":false,"feedback":true,"schema_version":1}` {
		t.Fatalf("canonical = %q", canonical)
	}
	for _, payload := range []string{
		``,
		`{"schema_version":1,"events":true}`,
		`{"schema_version":1,"events":1,"feedback":false}`,
		`{"schema_version":2,"events":true,"feedback":false}`,
		`{"schema_version":1,"events":true,"feedback":false,"other":true}`,
	} {
		if _, err := resource.ValidateExactJSONDocument([]byte(payload)); err == nil {
			t.Fatalf("invalid desired document accepted: %q", payload)
		}
	}
}

func TestLoadAcceptsExactJSONDocumentOnlyInBundleSchemaV4(t *testing.T) {
	root := writeExactJSONFixture(t)
	release, err := releasecontract.Load(root)
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	resource := release.Resources[0]
	if !resource.SupportsApply() ||
		resource.ExactJSONExemplar !=
			`{"events":false,"feedback":false,"schema_version":1}` {
		t.Fatalf("exact resource = %#v", resource)
	}

	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 2
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("schema v2 accepted an exact JSON document")
	}
}

func TestLoadRejectsExactJSONDocumentOverlappingInstallTarget(t *testing.T) {
	root := writeExactJSONFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["install_units"].([]any)[0].(map[string]any)["target"] =
		map[string]any{
			"root": "codex-config",
			"path": "mainframe/diagnostics.json",
		}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("exact JSON target overlapping an install target was accepted")
	}
}

func TestLoadEnforcesExactJSONDocumentResourceExclusivity(t *testing.T) {
	tests := map[string]struct {
		other   map[string]any
		wantErr bool
	}{
		"JSON claim on exact target": {
			other: map[string]any{
				"id":                  "codex.events",
				"strategy":            "json-key-merge",
				"source":              "diagnostics.json",
				"target":              map[string]any{"root": "codex-config", "path": "mainframe/diagnostics.json"},
				"observation":         "supported",
				"apply":               "unimplemented",
				"owned_json_pointers": []any{"/events"},
			},
			wantErr: true,
		},
		"directory ancestor": {
			other: map[string]any{
				"id":          "codex.directory",
				"strategy":    "ensure-directory",
				"target":      map[string]any{"root": "codex-config", "path": "mainframe"},
				"observation": "supported",
				"apply":       "unimplemented",
			},
			wantErr: false,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			root := writeExactJSONFixture(t)
			manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
			manifest := readObject(t, manifestPath)
			resources := manifest["resources"].([]any)
			resources = append(resources, test.other)
			if test.other["id"].(string) < resources[0].(map[string]any)["id"].(string) {
				resources[0], resources[1] = resources[1], resources[0]
			}
			manifest["resources"] = resources
			writeJSON(t, manifestPath, manifest, 0o644)
			rewriteIndexDigest(t, root, manifestPath)
			_, err := releasecontract.Load(root)
			if (err != nil) != test.wantErr {
				t.Fatalf("Load() error = %v, wantErr %t", err, test.wantErr)
			}
		})
	}
}

func TestLoadRejectsMCPProjectionOnExactJSONDocumentTarget(t *testing.T) {
	root := writeExactJSONFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	projection := validCodexMCPProjectionRecord()
	projection["target"] = map[string]any{
		"root": "codex-config",
		"path": "mainframe/diagnostics.json",
	}
	manifest["mcp_projections"] = []any{projection}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	if _, err := releasecontract.Load(root); err == nil {
		t.Fatal("MCP projection on exact JSON target was accepted")
	}
}

func writeExactJSONFixture(t *testing.T) string {
	t.Helper()
	root := writeFixture(t)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	manifest["schema_version"] = 4
	diagnosticsPath := filepath.Join(
		root,
		"bundles/codex/diagnostics.json",
	)
	writeFile(
		t,
		diagnosticsPath,
		`{"events":false,"feedback":false,"schema_version":1}`+"\n",
		0o644,
	)
	manifest["resources"] = []any{map[string]any{
		"id":       "codex.diagnostics",
		"strategy": "exact-json-document",
		"source":   "diagnostics.json",
		"target": map[string]any{
			"root": "codex-config",
			"path": "mainframe/diagnostics.json",
		},
		"observation": "supported",
		"apply":       "supported",
	}}
	manifest["payload_files"] = []any{
		payloadRow(
			t,
			filepath.Join(root, "bundles/codex/config.json"),
			"config.json",
		),
		payloadRow(t, diagnosticsPath, "diagnostics.json"),
		payloadRow(
			t,
			filepath.Join(root, "bundles/codex/payload.txt"),
			"payload.txt",
		),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	return root
}

func exactJSONResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "codex.diagnostics", ComponentID: domain.ComponentCodex,
		Strategy:   releasecontract.StrategyExactJSONDocument,
		SourcePath: "bundles/codex/diagnostics.json",
		Target: domain.Location{
			Root: domain.RootCodexConfig, Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
}

func applySupportedResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "opencode.permissions", ComponentID: domain.ComponentOpenCode,
		Strategy:    releasecontract.StrategyJSONKeyMerge,
		Target:      domain.Location{Root: domain.RootOpenCodeConfig, Path: "opencode.json"},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportSupported,
		JSONMapOwnership: &releasecontract.JSONMapOwnership{
			MapPointer: "/permission", EntrySchema: "decision-rule-v1",
			DesiredMap: `{"bash":{"*":"deny"}}`,
			RegistryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-permissions.json",
			},
			RegistrySchemaVersion: 1, EntriesPointer: "/actions",
		},
	}
}

func writeApplySupportedOwnershipFixture(
	t *testing.T,
	component string,
	targetRoot string,
) string {
	t.Helper()
	root := writeOwnershipFixture(t)
	rewriteFixtureTargets(t, root, component, targetRoot)
	manifestPath := filepath.Join(root, "bundles/codex/bundle.json")
	manifest := readObject(t, manifestPath)
	resource := manifest["resources"].([]any)[0].(map[string]any)
	resource["target"] = map[string]any{"root": targetRoot, "path": "opencode.json"}
	resource["apply"] = "supported"
	ownership := resource["ownership"].(map[string]any)
	ownership["map_pointer"] = "/permission"
	ownership["registry"].(map[string]any)["target"] = map[string]any{
		"root": targetRoot, "path": "opencode.json.mainframe-permissions.json",
	}
	configPath := filepath.Join(root, "bundles/codex/config.json")
	writeFile(t, configPath, `{"permission":{"bash":{"*":"deny"}}}`+"\n", 0o644)
	manifest["payload_files"] = []any{
		payloadRow(t, configPath, "config.json"),
		payloadRow(t, filepath.Join(root, "bundles/codex/payload.txt"), "payload.txt"),
	}
	writeJSON(t, manifestPath, manifest, 0o644)
	rewriteIndexDigest(t, root, manifestPath)
	return root
}
