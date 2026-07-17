package releasecontract

import (
	"encoding/json"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type mcpProjectionCodecContract struct {
	target          domain.Location
	mapPointer      string
	registryTarget  domain.Location
	registryPointer string
	documentFormat  MCPProjectionDocumentFormat
	entryType       string
}

func mcpProjectionContract(
	component domain.ComponentID,
	codec MCPProjectionCodec,
) (mcpProjectionCodecContract, bool) {
	switch {
	case component == domain.ComponentClaudeCode && codec == MCPProjectionClaudeUserHTTP:
		return mcpProjectionCodecContract{
			target: domain.Location{
				Root: domain.RootHome, Path: ".claude.json",
			},
			mapPointer: "/mcpServers",
			registryTarget: domain.Location{
				Root: domain.RootClaudeConfig, Path: "mainframe/mcp-ownership.json",
			},
			registryPointer: "/servers",
			documentFormat:  MCPProjectionDocumentJSON,
			entryType:       "http",
		}, true
	case component == domain.ComponentCodex && codec == MCPProjectionCodexUserHTTP:
		return mcpProjectionCodecContract{
			target: domain.Location{
				Root: domain.RootCodexConfig, Path: "config.toml",
			},
			mapPointer: "/mcp_servers",
			registryTarget: domain.Location{
				Root: domain.RootCodexConfig, Path: "mainframe/mcp-ownership.json",
			},
			registryPointer: "/servers",
			documentFormat:  MCPProjectionDocumentTOML,
		}, true
	case component == domain.ComponentOpenCode && codec == MCPProjectionOpenCodeRemote:
		return mcpProjectionCodecContract{
			target: domain.Location{
				Root: domain.RootOpenCodeConfig, Path: "opencode.json",
			},
			mapPointer: "/mcp",
			registryTarget: domain.Location{
				Root: domain.RootOpenCodeConfig,
				Path: "opencode.json.mainframe-mcp.json",
			},
			registryPointer: "/servers",
			documentFormat:  MCPProjectionDocumentJSON,
			entryType:       "remote",
		}, true
	default:
		return mcpProjectionCodecContract{}, false
	}
}

func encodeMCPProjectionEntry(contract mcpProjectionCodecContract, endpoint string) (string, error) {
	entry := map[string]string{"url": endpoint}
	if contract.entryType != "" {
		entry["type"] = contract.entryType
	}
	desired, err := json.Marshal(entry)
	return string(desired), err
}
