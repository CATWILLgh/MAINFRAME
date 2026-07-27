package application

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

type MCPCredentialBinding struct {
	ServerID   mcpcatalog.ServerID
	ProfileID  mcpcatalog.ProfileID
	InstanceID credentialcatalog.InstanceID
}

func buildLifecycleRequest(
	snapshot Snapshot,
	request Request,
) (lifecycle.PreviewRequest, error) {
	credentials, err := resolveMCPCredentials(snapshot, request)
	if err != nil {
		return lifecycle.PreviewRequest{}, err
	}
	return lifecycle.PreviewRequest{
		Components:     append([]domain.ComponentID(nil), request.Components...),
		MCPSelections:  cloneSelections(request.MCPSelections),
		MCPCredentials: credentials,
		Diagnostics:    request.Diagnostics,
	}, nil
}

func resolveMCPCredentials(
	snapshot Snapshot,
	request Request,
) ([]mcpconfiguration.CredentialBinding, error) {
	if len(request.MCPCredentials) == 0 {
		return nil, nil
	}
	if snapshot.Credentials == nil {
		return nil, fmt.Errorf("credential snapshot is unavailable")
	}
	instances := snapshot.Credentials.Instances()
	if request.CredentialInstances != nil {
		instances = request.CredentialInstances.Clone()
	}
	seen := make(map[mcpcatalog.ServerID]bool)
	result := make([]mcpconfiguration.CredentialBinding, 0, len(request.MCPCredentials))
	for _, binding := range request.MCPCredentials {
		if seen[binding.ServerID] {
			return nil, fmt.Errorf(
				"duplicate MCP credential binding for server %q",
				binding.ServerID,
			)
		}
		seen[binding.ServerID] = true
		adapter, err := openCodeAdapterForBinding(request.MCPSelections, binding)
		if err != nil {
			return nil, err
		}
		secret, err := snapshot.Credentials.ResolveMCPSecret(
			instances,
			binding.ServerID,
			binding.ProfileID,
			binding.InstanceID,
		)
		if err != nil {
			return nil, fmt.Errorf(
				"resolve MCP credential binding for %q: %w",
				binding.ServerID,
				err,
			)
		}
		result = append(result, mcpconfiguration.CredentialBinding{
			ComponentID:         adapter,
			ServerID:            binding.ServerID,
			ProfileID:           binding.ProfileID,
			EnvironmentVariable: secret.Name,
		})
	}
	return result, nil
}

func openCodeAdapterForBinding(
	selections []mcpcatalog.Selection,
	binding MCPCredentialBinding,
) (domain.ComponentID, error) {
	for _, selection := range selections {
		if selection.ServerID != binding.ServerID ||
			selection.ProfileID != binding.ProfileID {
			continue
		}
		if len(selection.Adapters) != 1 ||
			selection.Adapters[0] != domain.ComponentOpenCode {
			return "", fmt.Errorf(
				"credential-bound MCP profile is currently supported only for OpenCode",
			)
		}
		return domain.ComponentOpenCode, nil
	}
	return "", fmt.Errorf(
		"MCP credential binding for %q has no matching selection",
		binding.ServerID,
	)
}
