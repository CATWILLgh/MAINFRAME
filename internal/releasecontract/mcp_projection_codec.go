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
			entryType:       "http",
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
			entryType:       "remote",
		}, true
	default:
		return mcpProjectionCodecContract{}, false
	}
}

func encodeMCPProjectionEntry(contract mcpProjectionCodecContract, endpoint string) (string, error) {
	desired, err := json.Marshal(map[string]string{
		"type": contract.entryType,
		"url":  endpoint,
	})
	return string(desired), err
}
