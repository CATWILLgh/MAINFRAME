package releasecontract

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

// SupportsApply reports whether the advertised capability matches a complete ownership contract.
func (resource Resource) SupportsApply() bool {
	if resource.Strategy == StrategyExactJSONDocument {
		return resource.supportsExactJSONDocumentApply()
	}
	return resource.supportsOpenCodeMapApply()
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
		domain.ComponentAntigravity2: domain.RootAntigravityConfig,
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
	if resource.Strategy == StrategyExactJSONDocument {
		return resource.SupportsApply()
	}
	return resource.Apply == SupportUnimplemented || resource.SupportsApply()
}
