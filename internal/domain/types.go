package domain

import (
	"path"
	"strings"
	"unicode"
)

type ComponentID string

const (
	ComponentClaudeCode          ComponentID = "claude-code"
	ComponentCodex               ComponentID = "codex"
	ComponentOpenCode            ComponentID = "opencode"
	ComponentCodexGates          ComponentID = "codex-gates"
	ComponentSharedGateDetectors ComponentID = "shared-gate-detectors"
)

type DesiredState struct {
	Components []ComponentID `json:"components"`
}

type ObservedState struct {
	Components []ObservedComponent `json:"components"`
}

type ObservedComponent struct {
	ID        ComponentID `json:"id"`
	Artifacts []Artifact  `json:"artifacts"`
}

type ArtifactPath string

func (artifactPath ArtifactPath) Valid() bool {
	value := string(artifactPath)
	if value == "" || value == "." || value == ".." || strings.HasPrefix(value, "../") {
		return false
	}
	if path.IsAbs(value) || path.Clean(value) != value {
		return false
	}
	if strings.ContainsRune(value, '\\') {
		return false
	}
	for _, character := range value {
		if unicode.IsControl(character) {
			return false
		}
	}
	return true
}

type Artifact struct {
	Path      ArtifactPath    `json:"path"`
	Ownership OwnershipStatus `json:"ownership,omitempty"`
}

type OwnershipStatus string

const (
	OwnershipManagedExact    OwnershipStatus = "managed_exact"
	OwnershipManagedDrifted  OwnershipStatus = "managed_drifted"
	OwnershipLegacyAdoptable OwnershipStatus = "legacy_adoptable"
	OwnershipForeign         OwnershipStatus = "foreign"
	OwnershipConflict        OwnershipStatus = "conflict"
)

func (status OwnershipStatus) Removable() bool {
	return status == OwnershipManagedExact
}

func (status OwnershipStatus) Valid() bool {
	switch status {
	case OwnershipManagedExact,
		OwnershipManagedDrifted,
		OwnershipLegacyAdoptable,
		OwnershipForeign,
		OwnershipConflict:
		return true
	default:
		return false
	}
}

type OperationKind string

const (
	OperationInstall  OperationKind = "install"
	OperationRemove   OperationKind = "remove"
	OperationConflict OperationKind = "conflict"
)

type Operation struct {
	ComponentID ComponentID   `json:"component_id"`
	Kind        OperationKind `json:"kind"`
	Artifact    Artifact      `json:"artifact"`
}

type Plan struct {
	Operations []Operation `json:"operations"`
}

type PlanRequest struct {
	Desired  DesiredState  `json:"desired"`
	Observed ObservedState `json:"observed"`
}
