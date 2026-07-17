package releasecontract

import (
	"encoding/json"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type mcpProjectionCodecContract struct {
	target                   domain.Location
	mapPointer               string
	registryTarget           domain.Location
	registryPointer          string
	documentFormat           MCPProjectionDocumentFormat
	endpointKey              string
	entryType                string
	materializationSupported bool
}

type mcpProjectionCodecKey struct {
	component domain.ComponentID
	codec     MCPProjectionCodec
}

var mcpProjectionContracts = map[mcpProjectionCodecKey]mcpProjectionCodecContract{
	{domain.ComponentAntigravity2, MCPProjectionAntigravityGlobalHTTP}: {
		target: domain.Location{
			Root: domain.RootAntigravityConfig, Path: "mcp_config.json",
		},
		mapPointer: "/mcpServers",
		registryTarget: domain.Location{
			Root: domain.RootAntigravityData, Path: "mainframe/mcp-ownership.json",
		},
		registryPointer:          "/servers",
		documentFormat:           MCPProjectionDocumentJSON,
		endpointKey:              "serverUrl",
		materializationSupported: true,
	},
	{domain.ComponentClaudeCode, MCPProjectionClaudeUserHTTP}: {
		target: domain.Location{
			Root: domain.RootHome, Path: ".claude.json",
		},
		mapPointer: "/mcpServers",
		registryTarget: domain.Location{
			Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
		},
		registryPointer:          "/servers",
		documentFormat:           MCPProjectionDocumentJSON,
		endpointKey:              "url",
		entryType:                "http",
		materializationSupported: true,
	},
	{domain.ComponentCodex, MCPProjectionCodexUserHTTP}: {
		target: domain.Location{
			Root: domain.RootCodexConfig, Path: "config.toml",
		},
		mapPointer: "/mcp_servers",
		registryTarget: domain.Location{
			Root: domain.RootCodexConfig, Path: "mainframe/mcp-ownership.json",
		},
		registryPointer:          "/servers",
		documentFormat:           MCPProjectionDocumentTOML,
		endpointKey:              "url",
		materializationSupported: true,
	},
	{domain.ComponentOpenCode, MCPProjectionOpenCodeRemote}: {
		target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "opencode.json",
		},
		mapPointer: "/mcp",
		registryTarget: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "opencode.json.mainframe-mcp.json",
		},
		registryPointer:          "/servers",
		documentFormat:           MCPProjectionDocumentJSON,
		endpointKey:              "url",
		entryType:                "remote",
		materializationSupported: true,
	},
}

// SupportsMaterialization covers emitted intents; adapter deselection remains planner policy.
func (projection MCPProjection) SupportsMaterialization() bool {
	contract, exists := mcpProjectionContract(projection.ComponentID, projection.Codec)
	return exists && contract.materializationSupported
}

func mcpProjectionContract(
	component domain.ComponentID,
	codec MCPProjectionCodec,
) (mcpProjectionCodecContract, bool) {
	contract, exists := mcpProjectionContracts[mcpProjectionCodecKey{
		component: component, codec: codec,
	}]
	return contract, exists
}

func encodeMCPProjectionEntry(contract mcpProjectionCodecContract, endpoint string) (string, error) {
	entry := map[string]string{contract.endpointKey: endpoint}
	if contract.entryType != "" {
		entry["type"] = contract.entryType
	}
	desired, err := json.Marshal(entry)
	return string(desired), err
}
