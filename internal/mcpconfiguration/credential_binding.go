package mcpconfiguration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type CredentialBinding struct {
	ComponentID         domain.ComponentID
	ServerID            mcpcatalog.ServerID
	ProfileID           mcpcatalog.ProfileID
	EnvironmentVariable string
}

func (inspection Inspection) WithCredentialBindings(
	bindings []CredentialBinding,
) (Inspection, error) {
	bound := inspection
	bound.projections = append(
		[]releasecontract.MCPProjection(nil),
		inspection.projections...,
	)
	seen := make(map[domain.ComponentID]map[mcpcatalog.ServerID]bool)
	for _, binding := range bindings {
		if duplicateCredentialBinding(seen, binding) {
			return Inspection{}, fmt.Errorf(
				"duplicate MCP credential binding for %q and %q",
				binding.ComponentID,
				binding.ServerID,
			)
		}
		index, exists := bound.credentialProjectionIndex(binding)
		if !exists {
			return Inspection{}, fmt.Errorf(
				"MCP credential binding has no adapter-local projection",
			)
		}
		projection, err := releasecontract.BindMCPProjectionProfile(
			bound.projections[index],
			bound.catalog,
			binding.ProfileID,
			binding.EnvironmentVariable,
		)
		if err != nil {
			return Inspection{}, fmt.Errorf(
				"bind MCP credential projection: %w",
				err,
			)
		}
		bound.projections[index] = projection
	}
	return bound, nil
}

func duplicateCredentialBinding(
	seen map[domain.ComponentID]map[mcpcatalog.ServerID]bool,
	binding CredentialBinding,
) bool {
	servers := seen[binding.ComponentID]
	if servers == nil {
		servers = make(map[mcpcatalog.ServerID]bool)
		seen[binding.ComponentID] = servers
	}
	if servers[binding.ServerID] {
		return true
	}
	servers[binding.ServerID] = true
	return false
}

func (inspection Inspection) credentialProjectionIndex(
	binding CredentialBinding,
) (int, bool) {
	for index, projection := range inspection.projections {
		if projection.ComponentID == binding.ComponentID &&
			projection.ServerID == binding.ServerID {
			return index, true
		}
	}
	return 0, false
}
