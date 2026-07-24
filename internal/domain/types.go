package domain

import (
	"path"
	"strings"
	"unicode"
	"unicode/utf8"
)

type ComponentID string

type FeatureID string

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

const FeatureHarnessFeedback FeatureID = "dev.harness-feedback"

type DesiredState struct {
	Components []ComponentID `json:"components"`
	Features   []FeatureID   `json:"features,omitempty"`
}

func (feature FeatureID) Valid() bool {
	value := string(feature)
	if value == "" {
		return false
	}
	separator := false
	for index, character := range value {
		if index == 0 && (character < 'a' || character > 'z') {
			return false
		}
		if character == '.' || character == '-' {
			if separator {
				return false
			}
			separator = true
			continue
		}
		if (character < 'a' || character > 'z') &&
			(character < '0' || character > '9') {
			return false
		}
		separator = false
	}
	return !separator
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
	Location   Location        `json:"location"`
	UnitID     string          `json:"unit_id,omitempty"`
	Ownership  OwnershipStatus `json:"ownership,omitempty"`
	RawTarget  string          `json:"raw_target,omitempty"`
	LinkDevice uint64          `json:"link_device,omitempty"`
	LinkInode  uint64          `json:"link_inode,omitempty"`
}

type LinkIdentity struct {
	Device uint64 `json:"device"`
	Inode  uint64 `json:"inode"`
}

type OwnershipStatus string

const (
	OwnershipManagedExact    OwnershipStatus = "managed_exact"
	OwnershipManagedPrevious OwnershipStatus = "managed_previous"
	OwnershipManagedDrifted  OwnershipStatus = "managed_drifted"
	OwnershipManagedMissing  OwnershipStatus = "managed_missing"
	OwnershipExactAdoptable  OwnershipStatus = "exact_adoptable"
	OwnershipLegacyAdoptable OwnershipStatus = "legacy_adoptable"
	OwnershipForeign         OwnershipStatus = "foreign"
	OwnershipConflict        OwnershipStatus = "conflict"
)

func (status OwnershipStatus) Removable() bool {
	return status == OwnershipManagedExact || status == OwnershipManagedPrevious
}

func (status OwnershipStatus) Managed() bool {
	switch status {
	case OwnershipManagedExact,
		OwnershipManagedPrevious,
		OwnershipManagedDrifted,
		OwnershipManagedMissing:
		return true
	default:
		return false
	}
}

func (component ObservedComponent) Managed() bool {
	for _, artifact := range component.Artifacts {
		if artifact.UnitID != "" && artifact.Ownership.Managed() {
			return true
		}
	}
	return false
}

func (status OwnershipStatus) Valid() bool {
	switch status {
	case OwnershipManagedExact,
		OwnershipManagedPrevious,
		OwnershipManagedDrifted,
		OwnershipManagedMissing,
		OwnershipExactAdoptable,
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
	OperationInstall    OperationKind = "install"
	OperationAdopt      OperationKind = "adopt"
	OperationReplace    OperationKind = "replace"
	OperationRemove     OperationKind = "remove"
	OperationRelinquish OperationKind = "relinquish"
	OperationConflict   OperationKind = "conflict"
)

type Operation struct {
	ComponentID ComponentID   `json:"component_id"`
	UnitID      string        `json:"unit_id,omitempty"`
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
