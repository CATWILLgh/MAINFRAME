package tui

type screen uint8

const (
	screenMain screen = iota
	screenSelection
	screenMCP
	screenMCPDetail
	screenMCPCredential
	screenDiagnostics
	screenCredentials
	screenCredentialLegacy
	screenCredentialLegacyPreview
	screenCredentialLegacyGroup
	screenCredentialLegacyPlan
	screenCredentialLegacyPlanGroup
	screenCredentialLegacyDraftAction
	screenCredentialLegacyDraftCreate
	screenCredentialLegacyDraftReview
	screenCredentialEdit
	screenSecretCreate
	screenSecretCreateConfirm
	screenApplyConfirm
	screenApplied
	screenReleases
	screenReleaseImport
	screenReleaseConfirm
	screenPreview
)
