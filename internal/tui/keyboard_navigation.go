package tui

import tea "charm.land/bubbletea/v2"

func (model *Model) handleGlobalKey(key tea.KeyPressMsg) (*Model, tea.Cmd, bool) {
	switch key.String() {
	case "q":
		if model.screen == screenMCPCredential ||
			model.screen == screenSecretCreate {
			return model, nil, false
		}
		model.clearReviewedPlan()
		model.discardSecretDraft()
		model.clearCredentialDrafts()
		model.clearLegacyReferencePreview()
		model.clearLegacyTransferPlan()
		return model, tea.Quit, true
	case "ctrl+c":
		model.clearReviewedPlan()
		model.discardSecretDraft()
		model.clearCredentialDrafts()
		model.clearLegacyReferencePreview()
		model.clearLegacyTransferPlan()
		return model, tea.Quit, true
	case "esc":
		updated, command := model.handleEscape()
		return updated, command, true
	case "b":
		if model.screen == screenSecretCreate {
			return model, nil, false
		}
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
	case screenCredentials:
		return model.openMain()
	case screenCredentialLegacy:
		return model.openCredentials()
	case screenCredentialLegacyPreview:
		model.clearLegacyReferencePreview()
		return model.openLegacyCredentialIndexes()
	case screenCredentialLegacyGroup:
		return model.openLegacyReferencePreviewMenu()
	case screenCredentialLegacyPlan:
		model.clearLegacyTransferPlan()
		return model.openLegacyCredentialIndexes()
	case screenCredentialLegacyPlanGroup:
		return model.openLegacyTransferPlanMenu()
	case screenCredentialEdit:
		return model.openCredentials()
	case screenSecretCreate, screenSecretCreateConfirm:
		model.discardSecretDraft()
		return model.openCredentials()
	case screenApplyConfirm:
		model.screen = screenPreview
		return model, nil
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
	case screenCredentials:
		updated, command := model.openMain()
		return updated, command, true
	case screenCredentialLegacy:
		updated, command := model.openCredentials()
		return updated, command, true
	case screenCredentialLegacyPreview:
		model.clearLegacyReferencePreview()
		updated, command := model.openLegacyCredentialIndexes()
		return updated, command, true
	case screenCredentialLegacyGroup:
		updated, command := model.openLegacyReferencePreviewMenu()
		return updated, command, true
	case screenCredentialLegacyPlan:
		model.clearLegacyTransferPlan()
		updated, command := model.openLegacyCredentialIndexes()
		return updated, command, true
	case screenCredentialLegacyPlanGroup:
		updated, command := model.openLegacyTransferPlanMenu()
		return updated, command, true
	case screenCredentialEdit:
		updated, command := model.openCredentials()
		return updated, command, true
	case screenSecretCreate, screenSecretCreateConfirm:
		model.discardSecretDraft()
		updated, command := model.openCredentials()
		return updated, command, true
	case screenApplyConfirm:
		model.screen = screenPreview
		return model, nil, true
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
