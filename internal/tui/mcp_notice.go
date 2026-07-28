package tui

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const antigravityContext7KeyedNoticeText = "Antigravity uses its standard configuration storage for this connection because it does not support a secret reference in remote MCP headers."
const openCodeContext7KeyedNoticeText = "OpenCode resolves the selected key only during final Apply and stores it in a private OpenCode-only file referenced from opencode.json."

func (model *Model) reviewedMCPNotice() string {
	for _, connection := range model.mcpPreview.Connections {
		if isKeyedAntigravityConnection(connection) {
			return bannerStyle.Render(antigravityContext7KeyedNoticeText)
		}
		if isKeyedOpenCodeConnection(connection) {
			return bannerStyle.Render(openCodeContext7KeyedNoticeText)
		}
	}
	return ""
}

func isKeyedOpenCodeConnection(connection mcpcatalog.Connection) bool {
	return connection.ServerID == "context7" &&
		connection.Profile.ID == "remote-api-key" &&
		contains(connection.Adapters, domain.ComponentOpenCode)
}

func isKeyedAntigravityConnection(connection mcpcatalog.Connection) bool {
	return connection.ServerID == "context7" &&
		connection.Profile.ID == "remote-api-key" &&
		contains(connection.Adapters, domain.ComponentAntigravity2)
}
