package tui

import tea "charm.land/bubbletea/v2"

func (model *Model) handleGlobalKey(key tea.KeyPressMsg) (*Model, tea.Cmd, bool) {
	switch key.String() {
	case "q":
		if model.screen == screenMCPCredential {
			return model, nil, false
		}
		model.clearReviewedPlan()
		model.clearCredentialDrafts()
		return model, tea.Quit, true
	case "ctrl+c":
		model.clearReviewedPlan()
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
	case screenMain:
		model.clearCredentialDrafts()
		return model, tea.Quit
	case screenSelection:
		return model.continueFromSelection()
	case screenMCP:
		return model.openMain()
	case screenMCPDetail:
		return model.backToMCPList()
	case screenMCPCredential:
		return model.backToMCPDetail()
	case screenDiagnostics:
		return model.continueFromDiagnostics()
	default:
		return model.openMain()
	}
}

func (model *Model) handleBack() (*Model, tea.Cmd, bool) {
	switch model.screen {
	case screenSelection:
		updated, command := model.continueFromSelection()
		return updated, command, true
	case screenMCP:
		updated, command := model.openMain()
		return updated, command, true
	case screenDiagnostics:
		updated, command := model.continueFromDiagnostics()
		return updated, command, true
	case screenMCPCredential:
		return model, nil, false
	case screenMCPDetail:
		updated, command := model.backToMCPList()
		return updated, command, true
	case screenPreview:
		updated, command := model.openMain()
		return updated, command, true
	default:
		return model, nil, false
	}
}
