package mcpconfiguration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func (inspection Inspection) Prepare(
	components []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (configuration.PreparedPlan, error) {
	return inspection.PrepareWithPreservation(components, nil, selections)
}

func (inspection Inspection) PrepareWithPreservation(
	components []domain.ComponentID,
	preserved []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (configuration.PreparedPlan, error) {
	return inspection.PrepareOntoWithPreservation(
		configuration.PreparedPlan{}, components, preserved, selections,
	)
}

func (inspection Inspection) PrepareOnto(
	base configuration.PreparedPlan,
	components []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (configuration.PreparedPlan, error) {
	return inspection.PrepareOntoWithPreservation(base, components, nil, selections)
}

func (inspection Inspection) PrepareOntoWithPreservation(
	base configuration.PreparedPlan,
	components []domain.ComponentID,
	preserved []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (configuration.PreparedPlan, error) {
	plan, err := inspection.PlanWithPreservation(components, preserved, selections)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if requiresMigrationForMaterialIntent(plan) {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"MCP configuration migration is required before changing Antigravity MCP",
		)
	}
	if plan.Blocking {
		return configuration.PreparedPlan{}, fmt.Errorf("MCP configuration plan is blocked")
	}
	builder := newMCPPreparation(inspection, base)
	for _, intent := range plan.Intents {
		if intent.Kind == IntentReady {
			continue
		}
		projection, exists := inspection.projectionByID(intent.ProjectionID)
		if !exists {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"unknown MCP projection %q", intent.ProjectionID,
			)
		}
		if !projection.SupportsMaterialization() {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"MCP projection %q does not support materialization", projection.ID,
			)
		}
		if err := builder.apply(projection, intent); err != nil {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"prepare MCP projection %q: %w", projection.ID, err,
			)
		}
	}
	transitions, err := builder.transitions()
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	preconditions := base.Preconditions()
	if hasMaterialIntent(plan.Intents, domain.ComponentAntigravity2) {
		if precondition, exists := inspection.antigravityAliasPrecondition(); exists {
			preconditions = append(preconditions, precondition)
		}
	}
	return configuration.NewPreparedPlanWithMaterializations(
		transitions,
		preconditions,
		builder.secretMaterializations(plan),
	)
}
