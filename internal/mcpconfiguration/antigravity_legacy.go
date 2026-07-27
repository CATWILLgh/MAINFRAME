package mcpconfiguration

import (
	"encoding/json"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

var antigravityLegacyMCPLocation = domain.Location{
	Root: domain.RootAntigravityData,
	Path: "mcp_config.json",
}

const antigravityUnsafeComparisonReason = "Antigravity MCP configuration locations cannot be safely compared"

type migrationSnapshot struct {
	canonical mcpFileSnapshot
	legacy    mcpFileSnapshot
}

func (inspection *Inspection) captureAntigravityMigration(
	projections []releasecontract.MCPProjection,
	host Host,
) {
	for _, projection := range projections {
		if projection.ComponentID != domain.ComponentAntigravity2 ||
			projection.Codec != releasecontract.MCPProjectionAntigravityGlobalHTTP {
			continue
		}
		inspection.captureFile(antigravityLegacyMCPLocation, host)
		inspection.migrations[domain.ComponentAntigravity2] = migrationSnapshot{
			canonical: inspection.files[projection.Target],
			legacy:    inspection.files[antigravityLegacyMCPLocation],
		}
		return
	}
}

func (inspection Inspection) migrationAssessments(
	active map[domain.ComponentID]bool,
) []MigrationAssessment {
	if !active[domain.ComponentAntigravity2] {
		return nil
	}
	snapshot, exists := inspection.migrations[domain.ComponentAntigravity2]
	if !exists {
		return nil
	}
	assessment, exists := assessAntigravityMigration(snapshot)
	if !exists {
		return nil
	}
	return []MigrationAssessment{assessment}
}

func assessAntigravityMigration(
	snapshot migrationSnapshot,
) (MigrationAssessment, bool) {
	if isCanonicalAntigravityAlias(snapshot) {
		return canonicalAntigravityMigration(), true
	}
	if snapshot.legacy.problem != "" {
		return invalidLegacyMigration(
			"legacy Antigravity MCP configuration cannot be safely inspected",
		), true
	}
	if !snapshot.legacy.present {
		if !snapshot.canonical.present {
			return MigrationAssessment{}, false
		}
		return canonicalAntigravityMigration(), true
	}
	legacy, err := jsondocument.Parse(snapshot.legacy.raw)
	if err != nil {
		return invalidLegacyMigration(
			"legacy Antigravity MCP configuration JSON is invalid",
		), true
	}
	if !isAntigravityMCPDocument(legacy) {
		return invalidLegacyMigration(
			"legacy Antigravity MCP configuration structure is invalid",
		), true
	}
	if !snapshot.canonical.present && snapshot.canonical.problem == "" {
		return MigrationAssessment{
			ComponentID:       domain.ComponentAntigravity2,
			State:             MigrationLegacyOnly,
			Reason:            "only the legacy Antigravity MCP configuration location exists",
			RequiresMigration: true,
		}, true
	}
	if snapshot.canonical.problem != "" {
		return conflictingAntigravityMigration(antigravityUnsafeComparisonReason), true
	}
	canonical, err := jsondocument.Parse(snapshot.canonical.raw)
	if err != nil {
		return conflictingAntigravityMigration(antigravityUnsafeComparisonReason), true
	}
	if canonical.Canonical() == legacy.Canonical() {
		return MigrationAssessment{
			ComponentID:       domain.ComponentAntigravity2,
			State:             MigrationEquivalentDual,
			Reason:            "both Antigravity MCP configuration locations are equivalent",
			RequiresMigration: true,
		}, true
	}
	return conflictingAntigravityMigration(
		"Antigravity MCP configuration locations contain different data",
	), true
}

func isCanonicalAntigravityAlias(snapshot migrationSnapshot) bool {
	return snapshot.legacy.kind == hostfs.EntrySymlink &&
		snapshot.legacy.path != "" &&
		snapshot.legacy.symlinkTargetPath == snapshot.canonical.path &&
		snapshot.canonical.present &&
		snapshot.canonical.problem == ""
}

func (inspection Inspection) antigravityAliasPrecondition() (
	configuration.ReadPrecondition,
	bool,
) {
	snapshot, exists := inspection.migrations[domain.ComponentAntigravity2]
	if !exists || !isCanonicalAntigravityAlias(snapshot) {
		return configuration.ReadPrecondition{}, false
	}
	return configuration.ReadPrecondition{
		Kind:               configuration.ReadPreconditionSymlink,
		Target:             antigravityLegacyMCPLocation,
		Device:             snapshot.legacy.device,
		Inode:              snapshot.legacy.inode,
		BirthSeconds:       snapshot.legacy.birthSeconds,
		BirthNanoseconds:   snapshot.legacy.birthNanoseconds,
		ExpectedTargetPath: snapshot.legacy.symlinkTargetPath,
	}, true
}

func canonicalAntigravityMigration() MigrationAssessment {
	return MigrationAssessment{
		ComponentID: domain.ComponentAntigravity2,
		State:       MigrationCanonicalOnly,
		Reason:      "canonical Antigravity MCP configuration location is in use",
	}
}

func invalidLegacyMigration(reason string) MigrationAssessment {
	return MigrationAssessment{
		ComponentID:       domain.ComponentAntigravity2,
		State:             MigrationInvalidLegacy,
		Reason:            reason,
		RequiresMigration: true,
		Conflict:          true,
	}
}

func isAntigravityMCPDocument(document jsondocument.Document) bool {
	var root map[string]json.RawMessage
	if err := json.Unmarshal([]byte(document.Canonical()), &root); err != nil || root == nil {
		return false
	}
	serversRaw, exists := root["mcpServers"]
	if !exists {
		return true
	}
	var servers map[string]json.RawMessage
	return json.Unmarshal(serversRaw, &servers) == nil && servers != nil
}

func conflictingAntigravityMigration(reason string) MigrationAssessment {
	return MigrationAssessment{
		ComponentID:       domain.ComponentAntigravity2,
		State:             MigrationConflictingDual,
		Reason:            reason,
		RequiresMigration: true,
		Conflict:          true,
	}
}

func hasMaterialIntent(intents []Intent, component domain.ComponentID) bool {
	for _, intent := range intents {
		if intent.ComponentID == component && isMaterialIntent(intent.Kind) {
			return true
		}
	}
	return false
}

func requiresMigrationForMaterialIntent(plan Plan) bool {
	for _, migration := range plan.Migrations {
		if migration.RequiresMigration &&
			hasMaterialIntent(plan.Intents, migration.ComponentID) {
			return true
		}
	}
	return false
}
