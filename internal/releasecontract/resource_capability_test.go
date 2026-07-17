package releasecontract_test

import (
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

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
