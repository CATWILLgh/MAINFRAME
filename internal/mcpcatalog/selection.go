package mcpcatalog

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Selection struct {
	ServerID  ServerID
	ProfileID ProfileID
	Adapters  []domain.ComponentID
}

type OnboardingPreview struct {
	Connections []Connection
	Executable  bool
}

type Connection struct {
	ServerID   ServerID
	ServerName string
	Profile    Profile
	Adapters   []domain.ComponentID
}

func (catalog Catalog) Preview(
	selectedEnvironments []domain.ComponentID,
	selections []Selection,
) (OnboardingPreview, error) {
	selected, err := selectedAdapterSet(selectedEnvironments)
	if err != nil {
		return OnboardingPreview{}, err
	}
	seenServers := make(map[ServerID]bool, len(selections))
	connections := make([]Connection, 0, len(selections))
	for _, selection := range selections {
		if seenServers[selection.ServerID] {
			return OnboardingPreview{}, fmt.Errorf("duplicate MCP server %q", selection.ServerID)
		}
		seenServers[selection.ServerID] = true
		connection, err := catalog.previewConnection(selected, selection)
		if err != nil {
			return OnboardingPreview{}, err
		}
		connections = append(connections, connection)
	}
	sort.Slice(connections, func(i, j int) bool {
		return connections[i].ServerID < connections[j].ServerID
	})
	return OnboardingPreview{Connections: connections, Executable: false}, nil
}

func (catalog Catalog) previewConnection(
	selected map[domain.ComponentID]bool,
	selection Selection,
) (Connection, error) {
	server, exists := catalog.Server(selection.ServerID)
	if !exists {
		return Connection{}, fmt.Errorf("unknown MCP server %q", selection.ServerID)
	}
	profile, exists := server.Profile(selection.ProfileID)
	if !exists {
		return Connection{}, fmt.Errorf(
			"MCP server %q has unknown profile %q",
			selection.ServerID, selection.ProfileID,
		)
	}
	adapters, err := validateSelectedAdapters(selected, profile, selection.Adapters)
	if err != nil {
		return Connection{}, fmt.Errorf("MCP server %q: %w", selection.ServerID, err)
	}
	return Connection{
		ServerID: server.ID, ServerName: server.Name,
		Profile: profile, Adapters: adapters,
	}, nil
}

func selectedAdapterSet(adapters []domain.ComponentID) (map[domain.ComponentID]bool, error) {
	selected := make(map[domain.ComponentID]bool, len(adapters))
	for _, adapter := range adapters {
		if !knownAdapter(adapter) {
			return nil, fmt.Errorf("component %q is not an MCP adapter", adapter)
		}
		if selected[adapter] {
			return nil, fmt.Errorf("duplicate selected environment %q", adapter)
		}
		selected[adapter] = true
	}
	return selected, nil
}

func validateSelectedAdapters(
	selected map[domain.ComponentID]bool,
	profile Profile,
	adapters []domain.ComponentID,
) ([]domain.ComponentID, error) {
	if len(adapters) == 0 {
		return nil, fmt.Errorf("profile %q requires at least one adapter", profile.ID)
	}
	seen := make(map[domain.ComponentID]bool, len(adapters))
	result := append([]domain.ComponentID(nil), adapters...)
	for _, adapter := range result {
		if seen[adapter] {
			return nil, fmt.Errorf("adapter %q is selected more than once", adapter)
		}
		seen[adapter] = true
		if !selected[adapter] {
			return nil, fmt.Errorf("adapter %q is not a selected environment", adapter)
		}
		status, reason := profile.Support(adapter)
		if status != Supported {
			return nil, fmt.Errorf("adapter %q is unsupported: %s", adapter, reason)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i] < result[j] })
	return result, nil
}
