package credentialmigration

import (
	"bytes"
	"errors"
	"io/fs"

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

type UnsafeReason string

const (
	ReasonSymbolicLink     UnsafeReason = "symbolic-link"
	ReasonNotRegular       UnsafeReason = "not-regular"
	ReasonUnsafeMode       UnsafeReason = "unsafe-mode"
	ReasonInspectionFailed UnsafeReason = "inspection-failed"
)

type Inventory struct {
	ReleaseID          string        `json:"release_id"`
	ReleaseIndexSHA256 string        `json:"release_index_sha256"`
	Indexes            []LegacyIndex `json:"indexes"`
}

type LegacyIndex struct {
	ComponentID            domain.ComponentID `json:"component_id"`
	ResourceID             string             `json:"resource_id"`
	Location               domain.Location    `json:"location"`
	State                  IndexState         `json:"state"`
	SizeBytes              int                `json:"size_bytes,omitempty"`
	MatchesCurrentTemplate bool               `json:"matches_current_release_template,omitempty"`
	UnsafeReason           UnsafeReason       `json:"unsafe_reason,omitempty"`
}

type Inspector interface {
	Inspect(domain.Location, bool) (hostfs.Entry, error)
}

type legacyResourceDescriptor struct {
	componentID domain.ComponentID
	resourceID  string
}

var legacyResourceDescriptors = []legacyResourceDescriptor{
	{
		componentID: domain.ComponentClaudeCode,
		resourceID:  "claude-code.credentials-index",
	},
	{
		componentID: domain.ComponentCodex,
		resourceID:  "codex.credentials-index",
	},
	{
		componentID: domain.ComponentOpenCode,
		resourceID:  "opencode.credentials-index",
	},
	{
		componentID: domain.ComponentAntigravity2,
		resourceID:  "antigravity-2.credentials-index",
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
		indexes[index] = inspectLegacyIndex(resource, inspector)
	}
	return Inventory{
		ReleaseID:          release.ID,
		ReleaseIndexSHA256: release.IndexSHA256,
		Indexes:            indexes,
	}, nil
}

func legacyResources(
	resources []releasecontract.Resource,
) ([]releasecontract.Resource, error) {
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

func matchingLegacyResources(
	resources []releasecontract.Resource,
	descriptor legacyResourceDescriptor,
) []releasecontract.Resource {
	var matches []releasecontract.Resource
	for _, resource := range resources {
		if resource.ID == descriptor.resourceID &&
			resource.ComponentID == descriptor.componentID &&
			resource.Strategy == releasecontract.StrategySeedIfAbsent {
			matches = append(matches, resource)
		}
	}
	return matches
}

func inspectLegacyIndex(
	resource releasecontract.Resource,
	inspector Inspector,
) LegacyIndex {
	result := LegacyIndex{
		ComponentID: resource.ComponentID,
		ResourceID:  resource.ID,
		Location:    resource.Target,
	}
	entry, err := inspector.Inspect(resource.Target, true)
	if errors.Is(err, fs.ErrNotExist) {
		result.State = IndexMissing
		return result
	}
	if err != nil {
		result.State = IndexUnsafe
		result.UnsafeReason = ReasonInspectionFailed
		return result
	}
	if entry.Kind == hostfs.EntrySymlink {
		result.State = IndexUnsafe
		result.UnsafeReason = ReasonSymbolicLink
		return result
	}
	if entry.Kind != hostfs.EntryRegular {
		result.State = IndexUnsafe
		result.UnsafeReason = ReasonNotRegular
		return result
	}
	if entry.Mode != 0o600 {
		result.State = IndexUnsafe
		result.UnsafeReason = ReasonUnsafeMode
		return result
	}
	result.State = IndexPresent
	result.SizeBytes = len(entry.Content)
	result.MatchesCurrentTemplate = bytes.Equal(
		entry.Content,
		resource.SourceContent,
	)
	return result
}
