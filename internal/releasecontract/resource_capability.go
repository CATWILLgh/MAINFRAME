package releasecontract

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

// SupportsApply reports whether the advertised capability matches a complete ownership contract.
func (resource Resource) SupportsApply() bool {
	if resource.Strategy == StrategySeedIfAbsent {
		return resource.supportsManagedSeedApply()
	}
	if resource.Strategy == StrategyExactJSONDocument {
		return resource.supportsExactJSONDocumentApply()
	}
	if resource.JSONClaimOwnership != nil {
		return resource.supportsJSONClaimApply()
	}
	return resource.supportsOpenCodeMapApply()
}

func (resource Resource) supportsJSONClaimApply() bool {
	root, known := componentOwnedRoots[resource.ComponentID]
	ownership := resource.JSONClaimOwnership
	return known &&
		resource.Apply == SupportSupported &&
		resource.Strategy == StrategyJSONKeyMerge &&
		resource.Observation == SupportSupported &&
		resource.Target.Root == root &&
		len(resource.OwnedJSONFields) == 0 &&
		resource.JSONMapOwnership == nil && ownership != nil &&
		ownership.RegistryTarget.Root == root &&
		ownership.RegistrySchemaVersion == 1 &&
		len(ownership.Claims) > 0 && resource.ExternalState == nil
}

const (
	managedFileRegistryPath    = "mainframe/file-ownership.json"
	managedFileRegistryVersion = 1
)

// Pinning a component's ownership registry to the same root it seeds into keeps
// one component's records from claiming another component's files.
var componentOwnedRoots = map[domain.ComponentID]domain.RootID{
	"credential-tools":           domain.RootCredentialsConfig,
	domain.ComponentClaudeCode:   domain.RootClaudeConfig,
	domain.ComponentCodex:        domain.RootCodexConfig,
	domain.ComponentOpenCode:     domain.RootOpenCodeConfig,
	domain.ComponentAntigravity2: domain.RootAntigravityData,
	domain.ComponentZCodeDesktop: domain.RootZCodeConfig,
}

func (resource Resource) supportsManagedSeedApply() bool {
	root, known := componentOwnedRoots[resource.ComponentID]
	ownership := resource.FileOwnership
	return known &&
		resource.Apply == SupportSupported &&
		resource.Observation == SupportSupported &&
		resource.SourcePath != "" &&
		resource.SourceContent != nil &&
		resource.Target.Root == root &&
		resource.Target.Path != "" &&
		ownership != nil &&
		ownership.RegistryTarget == (domain.Location{
			Root: root, Path: managedFileRegistryPath,
		}) &&
		ownership.RegistrySchemaVersion == managedFileRegistryVersion &&
		len(resource.LegacySourceSuffixes) == 0 &&
		len(resource.OwnedJSONFields) == 0 &&
		resource.JSONMapOwnership == nil &&
		resource.JSONClaimOwnership == nil &&
		resource.ExternalState == nil
}

// SupportsPreparation reports whether validated release data can produce an immutable after-image.
func (resource Resource) SupportsPreparation() bool {
	if resource.Strategy != StrategySeedIfAbsent {
		return resource.SupportsApply()
	}
	if resource.FileOwnership != nil {
		return resource.SupportsApply()
	}
	root, supported := componentOwnedRoots[resource.ComponentID]
	return supported &&
		resource.Observation == SupportSupported &&
		resource.Apply == SupportUnimplemented &&
		resource.SourcePath != "" &&
		resource.SourceContent != nil &&
		resource.Target.Root == root &&
		len(resource.LegacySourceSuffixes) == 0 &&
		len(resource.OwnedJSONFields) == 0 &&
		resource.JSONMapOwnership == nil &&
		resource.JSONClaimOwnership == nil &&
		resource.ExternalState == nil
}

func (resource Resource) supportsOpenCodeMapApply() bool {
	ownership := resource.JSONMapOwnership
	return resource.Apply == SupportSupported &&
		resource.ComponentID == domain.ComponentOpenCode &&
		resource.Strategy == StrategyJSONKeyMerge &&
		resource.Observation == SupportSupported &&
		resource.Target.Root == domain.RootOpenCodeConfig &&
		len(resource.OwnedJSONFields) == 0 &&
		ownership != nil &&
		ownership.EntrySchema == decisionRuleSchema &&
		ownership.RegistryTarget.Root == domain.RootOpenCodeConfig &&
		ownership.RegistrySchemaVersion == registrySchemaVersion &&
		ownership.EntriesPointer == decisionRuleEntries &&
		resource.ExternalState == nil
}

func (resource Resource) supportsExactJSONDocumentApply() bool {
	expectedRoots := map[domain.ComponentID]domain.RootID{
		domain.ComponentClaudeCode:   domain.RootClaudeConfig,
		domain.ComponentCodex:        domain.RootCodexConfig,
		domain.ComponentOpenCode:     domain.RootOpenCodeConfig,
		domain.ComponentAntigravity2: domain.RootAntigravityData,
		domain.ComponentZCodeDesktop: domain.RootZCodeConfig,
	}
	root, supported := expectedRoots[resource.ComponentID]
	canonical, exemplarErr := canonicalDiagnosticsDocument(
		[]byte(resource.ExactJSONExemplar),
	)
	return supported &&
		resource.Apply == SupportSupported &&
		resource.Observation == SupportSupported &&
		resource.SourcePath != "" &&
		resource.Target.Root == root &&
		resource.Target.Path == "mainframe/diagnostics.json" &&
		exemplarErr == nil &&
		canonical == resource.ExactJSONExemplar &&
		len(resource.LegacySourceSuffixes) == 0 &&
		len(resource.OwnedJSONFields) == 0 &&
		resource.JSONMapOwnership == nil &&
		resource.ExternalState == nil
}

func validApplyDeclaration(resource Resource) bool {
	if resource.FileOwnership != nil {
		return resource.SupportsApply()
	}
	if resource.Strategy == StrategyExactJSONDocument {
		return resource.SupportsApply()
	}
	return resource.Apply == SupportUnimplemented || resource.SupportsApply()
}
