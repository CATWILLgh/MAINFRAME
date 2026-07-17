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

type Plan struct {
	Intents  []Intent
	Blocking bool
}
