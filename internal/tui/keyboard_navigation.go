package tui

import tea "charm.land/bubbletea/v2"

func (model *Model) handleGlobalKey(key tea.KeyPressMsg) (*Model, tea.Cmd, bool) {
	switch key.String() {
	case "q":
		if model.screen == screenMCPCredential {
			return model, nil, false
		}
		model.clearCredentialDrafts()
		return model, tea.Quit, true
	case "ctrl+c":
		model.clearCredentialDrafts()
		return model, tea.Quit, true
	case "esc":
		updated, command := model.handleEscape()
		return updated, command, true
	case "b":
		return model.handleBack()
	default:
		return model, nil, false
	}
}

func (model *Model) handleEscape() (*Model, tea.Cmd) {
	switch model.screen {
	case screenSelection:
		model.clearCredentialDrafts()
		return model, tea.Quit
	case screenMCP:
		return model.backToSelection()
	case screenMCPDetail:
		return model.backToMCPList()
	case screenMCPCredential:
		return model.backToMCPDetail()
	default:
		if len(model.selected) == 0 {
			return model.backToSelection()
		}
		return model.openMCP()
	}
}

func (model *Model) handleBack() (*Model, tea.Cmd, bool) {
	switch model.screen {
	case screenMCPCredential:
		return model, nil, false
	case screenMCP:
		updated, command := model.backToSelection()
		return updated, command, true
	case screenMCPDetail:
		updated, command := model.backToMCPList()
		return updated, command, true
	case screenPreview:
		if len(model.selected) == 0 {
			updated, command := model.backToSelection()
			return updated, command, true
		}
		updated, command := model.openMCP()
		return updated, command, true
	default:
		return model, nil, false
	}
}
