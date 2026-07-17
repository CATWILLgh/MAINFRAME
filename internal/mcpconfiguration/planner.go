package mcpconfiguration

import (
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func (inspection Inspection) Plan(
	components []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (Plan, error) {
	preview, err := inspection.catalog.Preview(components, selections)
	if err != nil {
		return Plan{}, err
	}
	desired, intents := inspection.resolveSelections(preview)
	blocking := false
	active := make(map[domain.ComponentID]bool, len(components))
	for _, component := range components {
		active[component] = true
	}
	for _, projection := range inspection.projections {
		if !active[projection.ComponentID] {
			continue
		}
		intent, exists, intentBlocking := inspection.projectionIntent(
			projection, desired[projection.ID],
		)
		if exists {
			intents = append(intents, intent)
		}
		blocking = blocking || intentBlocking
	}
	migrations := inspection.migrationAssessments(active)
	for _, migration := range migrations {
		blocking = blocking || migration.Conflict &&
			hasMaterialIntent(intents, migration.ComponentID)
	}
	sort.Slice(intents, func(left, right int) bool {
		if intents[left].ComponentID != intents[right].ComponentID {
			return intents[left].ComponentID < intents[right].ComponentID
		}
		return intents[left].ServerID < intents[right].ServerID
	})
	return Plan{Intents: intents, Migrations: migrations, Blocking: blocking}, nil
}

func (inspection Inspection) resolveSelections(
	preview mcpcatalog.OnboardingPreview,
) (map[string]bool, []Intent) {
	desired := make(map[string]bool)
	var unsupported []Intent
	for _, connection := range preview.Connections {
		for _, adapter := range connection.Adapters {
			projection, exists := inspection.findProjection(
				connection.ServerID, connection.Profile.ID, adapter,
			)
			if !exists {
				unsupported = append(unsupported, Intent{
					ComponentID: adapter, ServerID: connection.ServerID,
					ProfileID: connection.Profile.ID, Kind: IntentUnsupported,
					Reason: "exact adapter configuration projection is not implemented",
				})
				continue
			}
			desired[projection.ID] = true
		}
	}
	return desired, unsupported
}

func (inspection Inspection) projectionIntent(
	projection releasecontract.MCPProjection,
	selected bool,
) (Intent, bool, bool) {
	snapshot := inspection.snapshots[projection.ID]
	if snapshot.registryProblem != "" {
		return newIntent(
			projection, IntentConflict, snapshot.registryProblem,
		), true, true
	}
	if !selected && !snapshot.ownedPresent {
		return Intent{}, false, false
	}
	if snapshot.ownedTombstone {
		intent, exists := reconcile(projection, snapshot, selected)
		return intent, exists, false
	}
	if snapshot.configProblem != "" {
		return newIntent(
			projection, IntentConflict, snapshot.configProblem,
		), true, true
	}
	intent, exists := reconcile(projection, snapshot, selected)
	return intent, exists, intent.Kind == IntentConflict
}

func (inspection Inspection) findProjection(
	server mcpcatalog.ServerID,
	profile mcpcatalog.ProfileID,
	component domain.ComponentID,
) (releasecontract.MCPProjection, bool) {
	for _, projection := range inspection.projections {
		if projection.ServerID == server && projection.ProfileID == profile &&
			projection.ComponentID == component {
			return projection, true
		}
	}
	return releasecontract.MCPProjection{}, false
}

func reconcile(
	projection releasecontract.MCPProjection,
	snapshot projectionSnapshot,
	desired bool,
) (Intent, bool) {
	if snapshot.ownedTombstone {
		if desired {
			return newIntent(projection, IntentRelinquish, "ownership was relinquished"), true
		}
		return Intent{}, false
	}
	if snapshot.ownedPresent {
		if !snapshot.existingPresent || !snapshot.existingComparable ||
			!jsonEqual(snapshot.existingRaw, snapshot.ownedRaw) {
			return newIntent(projection, IntentRelinquish, "managed entry was changed or removed by the user"), true
		}
		if !desired {
			return newIntent(projection, IntentRemove, "managed entry is no longer selected"), true
		}
		if jsonEqual(snapshot.ownedRaw, projection.DesiredEntry) {
			return newIntent(projection, IntentReady, "managed entry already matches"), true
		}
		return newIntent(projection, IntentUpdate, "managed entry differs from selected profile"), true
	}
	if !desired {
		return Intent{}, false
	}
	if snapshot.existingPresent {
		return newIntent(projection, IntentConflict, "existing entry is user owned"), true
	}
	return newIntent(projection, IntentAdd, "selected entry is absent"), true
}

func jsonEqual(left, right string) bool {
	leftDocument, leftErr := jsondocument.Parse([]byte(left))
	rightDocument, rightErr := jsondocument.Parse([]byte(right))
	if leftErr != nil || rightErr != nil {
		return false
	}
	return leftDocument.Canonical() == rightDocument.Canonical()
}

func newIntent(
	projection releasecontract.MCPProjection,
	kind IntentKind,
	reason string,
) Intent {
	return Intent{
		ProjectionID: projection.ID, ComponentID: projection.ComponentID,
		ServerID: projection.ServerID, ProfileID: projection.ProfileID,
		Kind: kind, Reason: reason, Target: projection.Target,
	}
}

func (plan Plan) String() string {
	return fmt.Sprintf(
		"MCP plan with %d intents and %d migration assessments",
		len(plan.Intents), len(plan.Migrations),
	)
}
