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

func openCodeContext7Applicable(
	request Request,
	semantic lifecycle.Preview,
	preview executor.Preview,
) bool {
	if !exactOpenCodeContext7Request(request) ||
		len(semantic.Diagnostics.Intents) != 0 ||
		!openCodeMutationScope(semantic, preview) {
		return false
	}
	for _, intent := range semantic.MCP.Intents {
		if intent.ComponentID != domain.ComponentOpenCode ||
			intent.ServerID != "context7" {
			return false
		}
	}
	for _, migration := range semantic.MCP.Migrations {
		if migration.ComponentID != domain.ComponentOpenCode {
			return false
		}
	}
	return true
}

func exactOpenCodeContext7Request(request Request) bool {
	if !containsComponent(request.Components, domain.ComponentOpenCode) ||
		request.Diagnostics.Configured ||
		request.Diagnostics.Events ||
		request.Diagnostics.Feedback ||
		len(request.MCPSelections) != 1 ||
		len(request.MCPCredentials) != 1 {
		return false
	}
	selection := request.MCPSelections[0]
	credential := request.MCPCredentials[0]
	return selection.ServerID == "context7" &&
		selection.ProfileID == "remote-api-key" &&
		len(selection.Adapters) == 1 &&
		selection.Adapters[0] == domain.ComponentOpenCode &&
		credential.ServerID == selection.ServerID &&
		credential.ProfileID == selection.ProfileID
}

func openCodeMutationScope(
	semantic lifecycle.Preview,
	preview executor.Preview,
) bool {
	for _, operation := range preview.Plan.Operations {
		if operation.Kind == domain.OperationConflict ||
			operation.ComponentID != domain.ComponentOpenCode {
			return false
		}
	}
	for _, change := range semantic.Configuration.Changes {
		if change.ComponentID != domain.ComponentOpenCode {
			return false
		}
	}
	for _, transition := range preview.Configuration.Transitions() {
		for _, mutation := range transition.Mutations {
			if mutation.Target.Root != domain.RootOpenCodeConfig &&
				mutation.Target.Root != domain.RootCredentialsConfig {
				return false
			}
		}
	}
	for _, precondition := range preview.Configuration.Preconditions() {
		if precondition.Target.Root != domain.RootOpenCodeConfig &&
			precondition.Target.Root != domain.RootCredentialsConfig {
			return false
		}
	}
	return len(preview.Plan.Operations) > 0 ||
		len(preview.Configuration.Transitions()) > 0
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
