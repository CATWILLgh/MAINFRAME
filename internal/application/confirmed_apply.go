package application

import (
	"errors"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
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
	return service.applyReviewed(plan, true, true)
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
		preview.Configuration.HasPreparationOnly() ||
		!credentialMutationScope(adapter, request, semantic, preview) {
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
		return exactContext7Removal(request)
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
		return adapter, (adapter == domain.ComponentAntigravity2 ||
			adapter == domain.ComponentOpenCode) &&
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

func exactContext7Removal(
	request Request,
) (domain.ComponentID, bool) {
	if len(request.MCPCredentials) != 0 ||
		len(request.Components) != 1 {
		return "", false
	}
	adapter := request.Components[0]
	return adapter, adapter == domain.ComponentAntigravity2 ||
		adapter == domain.ComponentOpenCode
}

func credentialMutationScope(
	adapter domain.ComponentID,
	request Request,
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
		if change.ComponentID != adapter &&
			!managedSecretsStoreChange(change) {
			return false
		}
	}
	storeChange, hasStoreChange := managedSecretsStoreChangeKind(
		semantic.Configuration.Changes,
	)
	for _, transition := range preview.Configuration.Transitions() {
		if !credentialTransitionAllowed(
			adapter,
			request,
			transition,
			storeChange,
			hasStoreChange,
		) {
			return false
		}
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

func managedSecretsStoreChange(change configuration.Change) bool {
	return change.ResourceID == "credential-tools.secrets-store" &&
		change.ComponentID == domain.ComponentCredentialTools
}

func credentialTransitionAllowed(
	adapter domain.ComponentID,
	request Request,
	transition configuration.Transition,
	storeChange configuration.ChangeKind,
	hasStoreChange bool,
) bool {
	if len(transition.ResourceIDs) == 1 &&
		transition.ResourceIDs[0] == "credential-tools.secrets-store" {
		return hasStoreChange &&
			validManagedStoreTransition(storeChange, transition)
	}
	if len(transition.ResourceIDs) == 1 &&
		transition.ResourceIDs[0] == "credentials.instances" {
		if request.CredentialInstances == nil {
			return false
		}
		plan, err := configuration.NewPreparedPlan(
			[]configuration.Transition{transition},
		)
		if err != nil {
			return false
		}
		return credentialcatalog.ValidateInstancesOnlyPlan(
			plan,
			*request.CredentialInstances,
		) == nil
	}
	for _, resourceID := range transition.ResourceIDs {
		if resourceID == "credential-tools.secrets-store" {
			return false
		}
	}
	for _, mutation := range transition.Mutations {
		if mutation.Target.Root == domain.RootCredentialsConfig {
			return false
		}
		if !credentialMutationRootAllowed(adapter, mutation.Target.Root) {
			return false
		}
	}
	return true
}

func managedSecretsStoreChangeKind(
	changes []configuration.Change,
) (configuration.ChangeKind, bool) {
	var kind configuration.ChangeKind
	found := false
	for _, change := range changes {
		if !managedSecretsStoreChange(change) {
			continue
		}
		if found {
			return "", false
		}
		kind, found = change.Kind, true
	}
	return kind, found
}

func validManagedStoreTransition(
	kind configuration.ChangeKind,
	transition configuration.Transition,
) bool {
	target := domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: "secrets.env",
	}
	registry := domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: "mainframe/file-ownership.json",
	}
	mutations := make(map[domain.Location]configuration.MutationDisposition)
	for _, mutation := range transition.Mutations {
		if mutation.Target != target && mutation.Target != registry {
			return false
		}
		mutations[mutation.Target] = mutation.Disposition
	}
	registryPresent := mutations[registry] == configuration.MutationPresent
	switch kind {
	case configuration.ChangeAdd, configuration.ChangeUpdate:
		return mutations[target] == configuration.MutationPresent &&
			len(mutations) == len(transition.Mutations) &&
			(len(mutations) == 1 || registryPresent)
	case configuration.ChangeRemove:
		return mutations[target] == configuration.MutationRemoveManagedSecret &&
			registryPresent && len(mutations) == 2 &&
			len(transition.Mutations) == 2
	case configuration.ChangeRelinquish:
		return registryPresent && len(mutations) == 1 &&
			len(transition.Mutations) == 1
	default:
		return false
	}
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
