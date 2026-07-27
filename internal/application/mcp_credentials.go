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
	ComponentID domain.ComponentID
	ServerID    mcpcatalog.ServerID
	ProfileID   mcpcatalog.ProfileID
	InstanceID  credentialcatalog.InstanceID
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
	seen := make(map[string]bool)
	result := make([]mcpconfiguration.CredentialBinding, 0, len(request.MCPCredentials))
	for _, binding := range request.MCPCredentials {
		adapter, err := adapterForBinding(request.MCPSelections, binding)
		if err != nil {
			return nil, err
		}
		key := string(binding.ServerID) + "\x00" + string(adapter)
		if seen[key] {
			return nil, fmt.Errorf(
				"duplicate MCP credential binding for server %q and adapter %q",
				binding.ServerID, adapter,
			)
		}
		seen[key] = true
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

func adapterForBinding(
	selections []mcpcatalog.Selection,
	binding MCPCredentialBinding,
) (domain.ComponentID, error) {
	for _, selection := range selections {
		if selection.ServerID != binding.ServerID ||
			selection.ProfileID != binding.ProfileID {
			continue
		}
		if binding.ComponentID != "" {
			if !SupportsMCPCredentialBinding(binding.ComponentID) ||
				!containsAdapter(selection.Adapters, binding.ComponentID) {
				return "", fmt.Errorf(
					"credential-bound MCP adapter %q is not supported by the selection",
					binding.ComponentID,
				)
			}
			return binding.ComponentID, nil
		}
		if len(selection.Adapters) != 1 ||
			!SupportsMCPCredentialBinding(selection.Adapters[0]) {
			return "", fmt.Errorf(
				"credential-bound MCP profile requires one supported adapter",
			)
		}
		return selection.Adapters[0], nil
	}
	return "", fmt.Errorf(
		"MCP credential binding for %q has no matching selection",
		binding.ServerID,
	)
}

func containsAdapter(
	adapters []domain.ComponentID,
	expected domain.ComponentID,
) bool {
	for _, adapter := range adapters {
		if adapter == expected {
			return true
		}
	}
	return false
}

func SupportsMCPCredentialBinding(component domain.ComponentID) bool {
	return component == domain.ComponentOpenCode ||
		component == domain.ComponentAntigravity2
}
