package application

import (
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

func zcodeLifecycleApplicable(
	request Request,
	semantic lifecycle.Preview,
	preview executor.Preview,
) bool {
	if !exactZCodeLifecycleRequest(request) ||
		len(semantic.MCP.Intents) != 0 || len(semantic.MCP.Migrations) != 0 ||
		semantic.MCP.Blocking || len(semantic.Diagnostics.Intents) != 0 ||
		preview.Configuration.HasPreparationOnly() {
		return false
	}
	for _, operation := range preview.Plan.Operations {
		if operation.Kind == domain.OperationConflict ||
			!zcodeLifecycleComponent(operation.ComponentID) {
			return false
		}
	}
	for _, change := range semantic.Configuration.Changes {
		if !zcodeLifecycleChange(change) {
			return false
		}
	}
	storeChange, hasStoreChange := managedSecretsStoreChangeKind(
		semantic.Configuration.Changes,
	)
	for _, transition := range preview.Configuration.Transitions() {
		if !zcodeLifecycleTransition(transition, storeChange, hasStoreChange) {
			return false
		}
	}
	for _, precondition := range preview.Configuration.Preconditions() {
		if !zcodeLifecycleLocation(precondition.Target) {
			return false
		}
	}
	return len(preview.Plan.Operations) > 0 ||
		len(preview.Configuration.Transitions()) > 0
}

func exactZCodeLifecycleRequest(request Request) bool {
	if len(request.MCPSelections) != 0 || len(request.MCPCredentials) != 0 ||
		request.CredentialInstances != nil || request.Diagnostics.Configured ||
		request.Diagnostics.Events || request.Diagnostics.Feedback {
		return false
	}
	return len(request.Components) == 0 ||
		(len(request.Components) == 1 &&
			request.Components[0] == domain.ComponentZCodeDesktop)
}

func zcodeLifecycleComponent(component domain.ComponentID) bool {
	return component == domain.ComponentZCodeDesktop ||
		component == domain.ComponentCredentialTools ||
		component == domain.ComponentMainframeCLI
}

func zcodeLifecycleChange(change configuration.Change) bool {
	return change.ResourceID == "zcode-desktop.hooks" &&
		change.ComponentID == domain.ComponentZCodeDesktop ||
		managedSecretsStoreChange(change)
}

func zcodeLifecycleTransition(
	transition configuration.Transition,
	storeChange configuration.ChangeKind,
	hasStoreChange bool,
) bool {
	if transition.PreparationOnly || len(transition.ResourceIDs) != 1 {
		return false
	}
	if transition.ResourceIDs[0] == "credential-tools.secrets-store" {
		return hasStoreChange &&
			validManagedStoreTransition(storeChange, transition)
	}
	if transition.ResourceIDs[0] != "zcode-desktop.hooks" ||
		len(transition.Mutations) == 0 {
		return false
	}
	return allZCodeLifecycleLocations(transition.Mutations)
}

func allZCodeLifecycleLocations(mutations []configuration.FileMutation) bool {
	for _, mutation := range mutations {
		if !zcodeLifecycleLocation(mutation.Target) {
			return false
		}
	}
	return true
}

func zcodeLifecycleLocation(target domain.Location) bool {
	if configuration.IsJSONClaimRemovalTarget(target) {
		return true
	}
	return target.Root == domain.RootCredentialsConfig &&
		(target.Path == "secrets.env" ||
			target.Path == "mainframe/file-ownership.json")
}
