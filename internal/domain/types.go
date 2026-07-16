package domain

import (
	"path"
	"strings"
	"unicode"
	"unicode/utf8"
)

type ComponentID string

type RootID string

const (
	RootHome              RootID = "home"
	RootClaudeConfig      RootID = "claude-config"
	RootCodexConfig       RootID = "codex-config"
	RootOpenCodeConfig    RootID = "opencode-config"
	RootAntigravityConfig RootID = "antigravity-config"
	RootAntigravityData   RootID = "antigravity-data"
	RootUserBin           RootID = "user-bin"
	RootCredentialsConfig RootID = "credentials-config"
	RootCommonData        RootID = "common-data"
)

func (root RootID) Valid() bool {
	for index, character := range root {
		if index == 0 && (character < 'a' || character > 'z') {
			return false
		}
		if index > 0 && (character < 'a' || character > 'z') &&
			(character < '0' || character > '9') && character != '-' {
			return false
		}
	}
	return root != ""
}

const (
	ComponentClaudeCode          ComponentID = "claude-code"
	ComponentCodex               ComponentID = "codex"
	ComponentOpenCode            ComponentID = "opencode"
	ComponentAntigravity2        ComponentID = "antigravity-2"
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
	if value == "" || !utf8.ValidString(value) || value == "." || value == ".." || strings.HasPrefix(value, "../") {
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

func (artifactPath ArtifactPath) Portable() bool {
	if !artifactPath.Valid() {
		return false
	}
	for _, character := range artifactPath {
		if character > unicode.MaxASCII {
			return false
		}
	}
	return true
}

type Location struct {
	Root RootID       `json:"root"`
	Path ArtifactPath `json:"path"`
}

func (location Location) Valid() bool {
	return location.Root.Valid() && location.Path.Valid()
}

type Artifact struct {
	Location  Location        `json:"location"`
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
	SourcePath  ArtifactPath  `json:"source_path,omitempty"`
}

type Plan struct {
	Operations []Operation `json:"operations"`
}

type PlanRequest struct {
	Desired  DesiredState  `json:"desired"`
	Observed ObservedState `json:"observed"`
}
