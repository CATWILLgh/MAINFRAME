package hostcompatibility

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

type Status string

const (
	StatusSatisfied    Status = "satisfied"
	StatusMissing      Status = "missing"
	StatusIncompatible Status = "incompatible"
	StatusUnavailable  Status = "unavailable"
)

type Application struct {
	BundleIdentifier string
	Version          string
}

type ApplicationInventory struct {
	Available    bool
	Complete     bool
	Applications []Application
}

type Assessment struct {
	ComponentID      domain.ComponentID
	Status           Status
	DetectedVersions []string
	ExpectedVersions []string
}
