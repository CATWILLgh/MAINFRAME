package application

import (
	"errors"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func (service Service) ApplyConfirmed(
	plan ReviewedPlan,
) (executor.Result, error) {
	if !plan.reviewed {
		return executor.Result{}, errors.New("plan was not produced by Review")
	}
	if !plan.applicable {
		return executor.Result{}, errors.New("reviewed plan has no applicable changes")
	}
	return service.applyReviewed(plan, true)
}

func context7Applicable(
	request Request,
	semantic lifecycle.Preview,
	preview executor.Preview,
) bool {
	adapter, exact := exactContext7Request(request)
	if !exact ||
		len(semantic.Diagnostics.Intents) != 0 ||
		len(semantic.MCP.Intents) == 0 ||
		!credentialMutationScope(adapter, semantic, preview) {
		return false
	}
	for _, intent := range semantic.MCP.Intents {
		if intent.ComponentID != adapter ||
			intent.ServerID != "context7" {
			return false
		}
	}
	for _, migration := range semantic.MCP.Migrations {
		if migration.ComponentID != adapter {
			return false
		}
	}
	return true
}

func exactContext7Request(request Request) (domain.ComponentID, bool) {
	if request.Diagnostics.Configured ||
		request.Diagnostics.Events ||
		request.Diagnostics.Feedback {
		return "", false
	}
	if len(request.MCPSelections) == 0 {
		return exactAntigravityContext7Removal(request)
	}
	if len(request.MCPSelections) != 1 {
		return "", false
	}
	selection := request.MCPSelections[0]
	if selection.ServerID != "context7" ||
		len(selection.Adapters) != 1 {
		return "", false
	}
	adapter := selection.Adapters[0]
	if !SupportsMCPCredentialBinding(adapter) ||
		!containsComponent(request.Components, adapter) {
		return "", false
	}
	if selection.ProfileID == "remote-keyless" {
		return adapter, adapter == domain.ComponentAntigravity2 &&
			len(request.MCPCredentials) == 0
	}
	if selection.ProfileID != "remote-api-key" ||
		len(request.MCPCredentials) != 1 {
		return "", false
	}
	credential := request.MCPCredentials[0]
	return adapter, credential.ServerID == selection.ServerID &&
		credential.ProfileID == selection.ProfileID
}

func exactAntigravityContext7Removal(
	request Request,
) (domain.ComponentID, bool) {
	if len(request.MCPCredentials) != 0 ||
		len(request.Components) != 1 ||
		request.Components[0] != domain.ComponentAntigravity2 {
		return "", false
	}
	return domain.ComponentAntigravity2, true
}

func credentialMutationScope(
	adapter domain.ComponentID,
	semantic lifecycle.Preview,
	preview executor.Preview,
) bool {
	for _, operation := range preview.Plan.Operations {
		if operation.Kind == domain.OperationConflict ||
			operation.ComponentID != adapter {
			return false
		}
	}
	for _, change := range semantic.Configuration.Changes {
		if change.ComponentID != adapter {
			return false
		}
	}
	for _, transition := range preview.Configuration.Transitions() {
		for _, mutation := range transition.Mutations {
			if !credentialMutationRootAllowed(adapter, mutation.Target.Root) {
				return false
			}
		}
	}
	for _, precondition := range preview.Configuration.Preconditions() {
		if !credentialMutationRootAllowed(adapter, precondition.Target.Root) {
			return false
		}
	}
	return len(preview.Plan.Operations) > 0 ||
		len(preview.Configuration.Transitions()) > 0
}

func credentialMutationRootAllowed(
	adapter domain.ComponentID,
	root domain.RootID,
) bool {
	if root == domain.RootCredentialsConfig {
		return true
	}
	if adapter == domain.ComponentOpenCode {
		return root == domain.RootOpenCodeConfig
	}
	return adapter == domain.ComponentAntigravity2 &&
		(root == domain.RootAntigravityConfig ||
			root == domain.RootAntigravityData)
}

func containsComponent(
	components []domain.ComponentID,
	expected domain.ComponentID,
) bool {
	for _, component := range components {
		if component == expected {
			return true
		}
	}
	return false
}
