package tui

import (
	"fmt"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func (model *Model) continueFromSelection() (*Model, tea.Cmd) {
	if len(model.selected) == 0 {
		model.reconcileMCPChoices()
		return model.openPreview()
	}
	return model.openMCP()
}

func (model *Model) continueFromMCP() (*Model, tea.Cmd) {
	if model.mcpMenuChoice == mcpReviewPlan {
		return model.openPreview()
	}
	return model.openMCPDetail(mcpcatalog.ServerID(model.mcpMenuChoice))
}

func (model *Model) openMCPDetail(serverID mcpcatalog.ServerID) (*Model, tea.Cmd) {
	server, exists := model.catalog.Server(serverID)
	if !exists {
		model.err = fmt.Errorf("MCP integration %q is unavailable", serverID)
		return model.reinitializeCurrentForm()
	}
	model.ensureMCPChoices()
	model.screen = screenMCPDetail
	model.activeMCP = serverID
	model.err = nil
	model.form = mcpDetailForm(model.catalog, server, model.mcpChoices[serverID], model.selected)
	return model, model.form.Init()
}

func (model *Model) continueFromMCPDetail() (*Model, tea.Cmd) {
	server, exists := model.catalog.Server(model.activeMCP)
	if !exists {
		model.err = fmt.Errorf("MCP integration %q is unavailable", model.activeMCP)
		return model.openMCP()
	}
	choice := model.mcpChoices[server.ID]
	normalizeMCPChoice(server, choice)
	if choice.Enabled && profileRequiresCredential(server, choice.ProfileID) {
		return model.openMCPCredential(server.ID)
	}
	return model.backToMCPList()
}

func (model *Model) openMCPCredential(serverID mcpcatalog.ServerID) (*Model, tea.Cmd) {
	server, exists := model.catalog.Server(serverID)
	if !exists {
		model.err = fmt.Errorf("MCP integration %q is unavailable", serverID)
		return model.reinitializeCurrentForm()
	}
	model.screen = screenMCPCredential
	model.activeMCP = serverID
	model.err = nil
	model.form = mcpCredentialForm(server, model.mcpChoices[serverID])
	return model, model.form.Init()
}

func (model *Model) backToMCPDetail() (*Model, tea.Cmd) {
	server, exists := model.catalog.Server(model.activeMCP)
	if !exists {
		return model.openMCP()
	}
	model.screen = screenMCPDetail
	model.err = nil
	model.form = mcpDetailForm(model.catalog, server, model.mcpChoices[server.ID], model.selected)
	return model, model.form.Init()
}

func (model *Model) backToMCPList() (*Model, tea.Cmd) {
	if server, exists := model.catalog.Server(model.activeMCP); exists {
		normalizeMCPChoice(server, model.mcpChoices[server.ID])
	}
	model.screen = screenMCP
	model.activeMCP = ""
	model.err = nil
	model.form = mcpCatalogForm(model.catalog, model.mcpChoices, &model.mcpMenuChoice)
	return model, model.form.Init()
}
