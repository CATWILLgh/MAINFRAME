package configuration

import (
	"encoding/json"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func (builder *preparationBuilder) applyJSONClaims(
	resource releasecontract.Resource,
	state jsonClaimSnapshot,
	selected bool,
) error {
	reconciliation, err := reconcileJSONClaims(
		resource.JSONClaimOwnership,
		state,
		selected,
	)
	if err != nil {
		return err
	}
	if reconciliation.removeConfig {
		builder.removeAfter[resource.Target] = true
		builder.removeKinds[resource.Target] = MutationRemoveJSONClaimFile
		builder.touch[resource.Target] = true
	} else if reconciliation.configChanged {
		builder.rawAfter[resource.Target] = reconciliation.config.Indented()
		builder.touch[resource.Target] = true
	}
	if reconciliation.removeRegistry {
		target := resource.JSONClaimOwnership.RegistryTarget
		builder.removeAfter[target] = true
		builder.removeKinds[target] = MutationRemoveJSONClaimFile
		builder.touch[target] = true
	} else if reconciliation.registryChanged {
		payload, err := json.MarshalIndent(reconciliation.registry, "", "  ")
		if err != nil {
			return fmt.Errorf("encode JSON claim registry: %w", err)
		}
		builder.rawAfter[resource.JSONClaimOwnership.RegistryTarget] = append(payload, '\n')
		builder.touch[resource.JSONClaimOwnership.RegistryTarget] = true
	}
	group := builder.groups[resource.Target]
	if group == nil {
		group = make(map[string]bool)
		builder.groups[resource.Target] = group
	}
	group[resource.ID] = true
	builder.groupByTarget[resource.JSONClaimOwnership.RegistryTarget] = resource.Target
	return nil
}
