package mcpconfiguration

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type IntentKind string

const (
	IntentAdd         IntentKind = "add"
	IntentUpdate      IntentKind = "update"
	IntentRemove      IntentKind = "remove"
	IntentRelinquish  IntentKind = "relinquish"
	IntentConflict    IntentKind = "conflict"
	IntentReady       IntentKind = "ready"
	IntentUnsupported IntentKind = "unsupported"
)

type Intent struct {
	ProjectionID string
	ComponentID  domain.ComponentID
	ServerID     mcpcatalog.ServerID
	ProfileID    mcpcatalog.ProfileID
	Kind         IntentKind
	Reason       string
	Target       domain.Location
}

type MigrationState string

const (
	MigrationLegacyOnly      MigrationState = "legacy-only"
	MigrationCanonicalOnly   MigrationState = "canonical-only"
	MigrationEquivalentDual  MigrationState = "equivalent-dual"
	MigrationConflictingDual MigrationState = "conflicting-dual"
	MigrationInvalidLegacy   MigrationState = "invalid-legacy"
)

type MigrationAssessment struct {
	ComponentID       domain.ComponentID
	State             MigrationState
	Reason            string
	RequiresMigration bool
	Conflict          bool
}

type Plan struct {
	Intents    []Intent
	Migrations []MigrationAssessment
	Blocking   bool
}
