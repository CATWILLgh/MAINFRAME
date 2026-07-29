package tui

import tea "charm.land/bubbletea/v2"

func (model *Model) View() tea.View {
	var content string
	switch model.screen {
	case screenSelection:
		content = model.selectionView()
	case screenMCP:
		content = model.mcpView()
	case screenMCPDetail:
		content = model.mcpDetailView()
	case screenMCPCredential:
		content = model.mcpCredentialView()
	case screenDiagnostics:
		content = model.diagnosticsView()
	case screenCredentials:
		content = model.credentialsView()
	case screenCredentialLegacy:
		content = model.legacyCredentialIndexesView()
	case screenCredentialLegacyPreview:
		content = model.legacyCredentialReferencePreviewView()
	case screenCredentialLegacyGroup:
		content = model.legacyCredentialReferenceGroupView()
	case screenCredentialLegacyPlan:
		content = model.legacyCredentialTransferPlanView()
	case screenCredentialLegacyPlanGroup:
		content = model.legacyCredentialTransferPlanGroupView()
	case screenCredentialLegacyDraftAction:
		content = model.legacyTransferDraftActionView()
	case screenCredentialLegacyDraftCreate:
		content = model.legacyTransferDraftCreateView()
	case screenCredentialLegacyDraftReview:
		content = model.legacyTransferDraftReviewView()
	case screenCredentialEdit:
		content = model.credentialEditView()
	case screenSecretCreate:
		content = model.secretCreateView()
	case screenSecretCreateConfirm:
		content = model.secretCreateConfirmView()
	case screenApplyConfirm:
		content = model.applyConfirmView()
	case screenApplied:
		content = model.appliedView()
	case screenPreview:
		content = model.previewView()
	default:
		content = model.mainView()
	}
	view := tea.NewView(content)
	view.AltScreen = true
	view.WindowTitle = "MAINFRAME"
	return view
}
