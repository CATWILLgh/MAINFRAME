package releasecontract

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

// SupportsApply reports whether the advertised capability matches a complete ownership contract.
func (resource Resource) SupportsApply() bool {
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

func validApplyDeclaration(resource Resource) bool {
	return resource.Apply == SupportUnimplemented || resource.SupportsApply()
}
