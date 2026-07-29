package credentialmigration

import (
	"bytes"
	"errors"
	"io/fs"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type IndexState string

const (
	IndexMissing IndexState = "missing"
	IndexPresent IndexState = "present"
	IndexUnsafe  IndexState = "unsafe"
)

type Readiness string

const (
	ReadinessNoTransferRequired     Readiness = "no_transfer_required"
	ReadinessManualTransferRequired Readiness = "manual_transfer_required"
	ReadinessBlocked                Readiness = "blocked"
)

type SourceRole string

const (
	SourceRoleSharedOriginal SourceRole = "shared_original"
	SourceRoleAdapterCopy    SourceRole = "adapter_copy"
)

type UnsafeReason string

const (
	ReasonSymbolicLink     UnsafeReason = "symbolic-link"
	ReasonNotRegular       UnsafeReason = "not-regular"
	ReasonUnsafeMode       UnsafeReason = "unsafe-mode"
	ReasonMalformedContent UnsafeReason = "malformed-content"
	ReasonInspectionFailed UnsafeReason = "inspection-failed"
)

type Inventory struct {
	ReleaseID          string        `json:"release_id"`
	ReleaseIndexSHA256 string        `json:"release_index_sha256"`
	MigrationReadiness Readiness     `json:"migration_readiness"`
	Indexes            []LegacyIndex `json:"indexes"`
}

type LegacyIndex struct {
	ComponentID            domain.ComponentID `json:"component_id"`
	ResourceID             string             `json:"resource_id"`
	Location               domain.Location    `json:"location"`
	SourceRole             SourceRole         `json:"source_role"`
	State                  IndexState         `json:"state"`
	SizeBytes              int                `json:"size_bytes,omitempty"`
	MatchesCurrentTemplate bool               `json:"matches_current_release_template,omitempty"`
	UnsafeReason           UnsafeReason       `json:"unsafe_reason,omitempty"`
	MigrationReadiness     Readiness          `json:"migration_readiness"`
}

type Inspector interface {
	Inspect(domain.Location, bool) (hostfs.Entry, error)
}

type legacyResourceDescriptor struct {
	componentID domain.ComponentID
	resourceID  string
	sourceRole  SourceRole
	sourcePath  domain.ArtifactPath
	target      domain.Location
}

var legacyResourceDescriptors = []legacyResourceDescriptor{
	{
		componentID: domain.ComponentClaudeCode,
		resourceID:  "claude-code.credentials-index",
		sourceRole:  SourceRoleSharedOriginal,
		sourcePath:  "bundles/claude-code/credentials-index.md",
		target: domain.Location{
			Root: domain.RootClaudeConfig, Path: "credentials-index.md",
		},
	},
	{
		componentID: domain.ComponentCodex,
		resourceID:  "codex.credentials-index",
		sourceRole:  SourceRoleAdapterCopy,
		sourcePath:  "bundles/codex/credentials-index.md",
		target: domain.Location{
			Root: domain.RootCodexConfig, Path: "credentials-index.md",
		},
	},
	{
		componentID: domain.ComponentOpenCode,
		resourceID:  "opencode.credentials-index",
		sourceRole:  SourceRoleAdapterCopy,
		sourcePath:  "bundles/opencode/credentials-index.md",
		target: domain.Location{
			Root: domain.RootOpenCodeConfig, Path: "credentials-index.md",
		},
	},
	{
		componentID: domain.ComponentAntigravity2,
		resourceID:  "antigravity-2.credentials-index",
		sourceRole:  SourceRoleAdapterCopy,
		sourcePath:  "bundles/antigravity-2/credentials-index.md",
		target: domain.Location{
			Root: domain.RootAntigravityData, Path: "credentials-index.md",
		},
	},
}

func InspectLegacyIndexes(
	release releasecontract.Release,
	inspector Inspector,
) (Inventory, error) {
	resources, err := legacyResources(release.Resources)
	if err != nil {
		return Inventory{}, err
	}
	indexes := make([]LegacyIndex, len(resources))
	for index, resource := range resources {
		indexes[index] = inspectLegacyIndex(
			resource,
			legacyResourceDescriptors[index].sourceRole,
			inspector,
		)
	}
	return Inventory{
		ReleaseID:          release.ID,
		ReleaseIndexSHA256: release.IndexSHA256,
		MigrationReadiness: reduceReadiness(indexes),
		Indexes:            indexes,
	}, nil
}

func legacyResources(
	resources []releasecontract.Resource,
) ([]releasecontract.Resource, error) {
	if hasUnclassifiedLegacyResource(resources) {
		return nil, errors.New(
			"legacy credential index resources are incompatible with this release",
		)
	}
	result := make([]releasecontract.Resource, len(legacyResourceDescriptors))
	for index, descriptor := range legacyResourceDescriptors {
		matches := matchingLegacyResources(resources, descriptor)
		if len(matches) != 1 {
			return nil, errors.New(
				"legacy credential index resources are incompatible with this release",
			)
		}
		result[index] = matches[0]
	}
	return result, nil
}

func hasUnclassifiedLegacyResource(
	resources []releasecontract.Resource,
) bool {
	for _, resource := range resources {
		if resource.Strategy != releasecontract.StrategySeedIfAbsent ||
			!strings.HasSuffix(resource.ID, ".credentials-index") {
			continue
		}
		classified := false
		for _, descriptor := range legacyResourceDescriptors {
			if legacyResourceMatches(resource, descriptor) {
				classified = true
				break
			}
		}
		if !classified {
			return true
		}
	}
	return false
}

func matchingLegacyResources(
	resources []releasecontract.Resource,
	descriptor legacyResourceDescriptor,
) []releasecontract.Resource {
	var matches []releasecontract.Resource
	for _, resource := range resources {
		if legacyResourceMatches(resource, descriptor) {
			matches = append(matches, resource)
		}
	}
	return matches
}

func legacyResourceMatches(
	resource releasecontract.Resource,
	descriptor legacyResourceDescriptor,
) bool {
	return resource.ID == descriptor.resourceID &&
		resource.ComponentID == descriptor.componentID &&
		resource.Strategy == releasecontract.StrategySeedIfAbsent &&
		resource.SourcePath == descriptor.sourcePath &&
		resource.Target == descriptor.target
}

func inspectLegacyIndex(
	resource releasecontract.Resource,
	sourceRole SourceRole,
	inspector Inspector,
) LegacyIndex {
	result := LegacyIndex{
		ComponentID: resource.ComponentID,
		ResourceID:  resource.ID,
		Location:    resource.Target,
		SourceRole:  sourceRole,
	}
	entry, err := inspector.Inspect(resource.Target, true)
	if errors.Is(err, fs.ErrNotExist) {
		result.State = IndexMissing
		return legacyIndexWithReadiness(result)
	}
	if err != nil {
		result.State = IndexUnsafe
		result.UnsafeReason = ReasonInspectionFailed
		return legacyIndexWithReadiness(result)
	}
	if reason := legacyEntryUnsafeReason(entry); reason != "" {
		result.State = IndexUnsafe
		result.UnsafeReason = reason
		return legacyIndexWithReadiness(result)
	}
	result.State = IndexPresent
	result.SizeBytes = len(entry.Content)
	result.MatchesCurrentTemplate = bytes.Equal(
		entry.Content,
		resource.SourceContent,
	)
	return legacyIndexWithReadiness(result)
}

func legacyIndexWithReadiness(index LegacyIndex) LegacyIndex {
	switch {
	case index.State == IndexUnsafe:
		index.MigrationReadiness = ReadinessBlocked
	case index.State == IndexPresent && !index.MatchesCurrentTemplate:
		index.MigrationReadiness = ReadinessManualTransferRequired
	default:
		index.MigrationReadiness = ReadinessNoTransferRequired
	}
	return index
}

func reduceReadiness(indexes []LegacyIndex) Readiness {
	readiness := ReadinessNoTransferRequired
	for _, index := range indexes {
		if index.MigrationReadiness == ReadinessBlocked {
			return ReadinessBlocked
		}
		if index.MigrationReadiness == ReadinessManualTransferRequired {
			readiness = ReadinessManualTransferRequired
		}
	}
	return readiness
}
