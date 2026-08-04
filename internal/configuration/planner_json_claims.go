package configuration

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func planJSONClaims(
	plan *Plan,
	resource releasecontract.Resource,
	observation Observation,
	states map[string]jsonClaimSnapshot,
	selected map[domain.ComponentID]bool,
) {
	if observation.Status == Attention || observation.Status == NotAssessed {
		plan.Issues = append(plan.Issues, issueForObservation(resource, observation))
		return
	}
	state, exists := states[resource.ID]
	if !exists {
		plan.Issues = append(plan.Issues, Issue{ResourceID: resource.ID, ComponentID: resource.ComponentID, Kind: IssuePlanningUnavailable, Reason: observation.Reason})
		return
	}
	reconciliation, err := reconcileJSONClaims(resource.JSONClaimOwnership, state, selected[resource.ComponentID])
	if err != nil {
		plan.Issues = append(plan.Issues, Issue{ResourceID: resource.ID, ComponentID: resource.ComponentID, Kind: IssuePlanningUnavailable, Reason: JSONDocumentInvalid})
		return
	}
	if reconciliation.configChanged || reconciliation.registryChanged {
		kind := ChangeUpdate
		if !selected[resource.ComponentID] {
			kind = ChangeRemove
		}
		plan.Changes = append(plan.Changes, changeForResource(resource, kind, ""))
	}
}
