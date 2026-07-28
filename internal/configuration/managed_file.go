package configuration

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const managedFileRegistrySchemaVersion = 1

type digestHost interface {
	InspectDigest(domain.Location) (hostfs.Entry, error)
}

type managedFileClaim struct {
	ResourceID  string             `json:"resource_id"`
	ComponentID domain.ComponentID `json:"component_id"`
	Target      domain.Location    `json:"target"`
	SHA256      string             `json:"sha256"`
	Mode        uint32             `json:"mode"`
}

type managedFileRegistry struct {
	SchemaVersion int                `json:"schema_version"`
	Claims        []managedFileClaim `json:"claims"`
}

type managedFileSnapshot struct {
	target   fileSnapshot
	registry fileSnapshot
	claims   []managedFileClaim
	claim    *managedFileClaim
}

func planManagedFile(
	plan *Plan,
	resource releasecontract.Resource,
	observation Observation,
	state managedFileSnapshot,
	selected bool,
) {
	if observation.Status == Attention || observation.Status == NotAssessed {
		plan.Issues = append(plan.Issues, issueForObservation(resource, observation))
		return
	}
	if state.claim == nil {
		if selected && !state.target.present {
			plan.Changes = append(plan.Changes, changeForResource(resource, ChangeAdd, ""))
		}
		return
	}
	matchesClaim := state.target.present &&
		state.target.sha256 == state.claim.SHA256 &&
		state.target.mode == state.claim.Mode
	if !matchesClaim && state.target.present {
		plan.Changes = append(plan.Changes, changeForResource(resource, ChangeRelinquish, ""))
		return
	}
	if !selected {
		kind := ChangeRelinquish
		if matchesClaim {
			kind = ChangeRemove
		}
		plan.Changes = append(plan.Changes, changeForResource(resource, kind, ""))
		return
	}
	if !state.target.present {
		plan.Changes = append(plan.Changes, changeForResource(resource, ChangeAdd, ""))
	} else if sha256Hex(resource.SourceContent) != state.claim.SHA256 {
		plan.Changes = append(plan.Changes, changeForResource(resource, ChangeUpdate, ""))
	}
}

func (builder *preparationBuilder) applyManagedFile(
	resource releasecontract.Resource,
	state managedFileSnapshot,
	selected bool,
) error {
	claims := make([]managedFileClaim, 0, len(state.claims)+1)
	for _, claim := range state.claims {
		if claim.ResourceID != resource.ID {
			claims = append(claims, claim)
		}
	}
	matches := state.claim != nil && state.target.present &&
		state.target.sha256 == state.claim.SHA256 &&
		state.target.mode == state.claim.Mode
	desiredDigest := sha256Hex(resource.SourceContent)
	needsPublication := selected &&
		((state.claim == nil && !state.target.present) ||
			(state.claim != nil && !state.target.present) ||
			(matches && state.claim.SHA256 != desiredDigest))
	if needsPublication {
		builder.rawAfter[resource.Target] = append(
			[]byte(nil),
			resource.SourceContent...,
		)
		builder.touch[resource.Target] = true
		claims = append(claims, managedFileClaim{
			ResourceID: resource.ID, ComponentID: resource.ComponentID,
			Target: resource.Target, SHA256: desiredDigest,
			Mode: privateConfigurationMode,
		})
	}
	if !selected && matches {
		builder.removeAfter[resource.Target] = true
		builder.touch[resource.Target] = true
	}
	registryTarget := resource.FileOwnership.RegistryTarget
	registryAfter, err := encodeManagedRegistry(claims)
	if err != nil {
		return err
	}
	builder.rawAfter[registryTarget] = registryAfter
	builder.touch[registryTarget] = true
	builder.groups[resource.Target] = map[string]bool{resource.ID: true}
	builder.groupByTarget[registryTarget] = resource.Target
	return nil
}

func (builder *preparationBuilder) applySeed(
	resource releasecontract.Resource,
	selected bool,
) error {
	if !selected {
		return nil
	}
	snapshot, exists := builder.files[resource.Target]
	if !exists {
		return fmt.Errorf("target snapshot is unavailable")
	}
	if snapshot.present {
		return fmt.Errorf("seed target unexpectedly exists")
	}
	builder.rawAfter[resource.Target] = append(
		[]byte{},
		resource.SourceContent...,
	)
	builder.groups[resource.Target] = map[string]bool{resource.ID: true}
	builder.touch[resource.Target] = true
	builder.preparationOnly[resource.Target] = true
	return nil
}

func sha256Hex(content []byte) string {
	sum := sha256.Sum256(content)
	return hex.EncodeToString(sum[:])
}

func inspectManagedFile(
	resource releasecontract.Resource,
	host Host,
	registryCache map[domain.Location]fileSnapshot,
) (Observation, managedFileSnapshot) {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	target, reason, safe := inspectManagedTarget(resource.Target, host)
	if !safe {
		result.Status, result.Reason = Attention, reason
		return result, managedFileSnapshot{}
	}
	registry, claims, reason, safe := inspectManagedRegistry(
		resource.FileOwnership.RegistryTarget,
		host,
		registryCache,
	)
	if !safe {
		result.Status, result.Reason = Attention, reason
		return result, managedFileSnapshot{}
	}
	state := managedFileSnapshot{target: target, registry: registry, claims: claims}
	for index := range claims {
		if claims[index].ResourceID == resource.ID {
			claim := claims[index]
			if claim.ComponentID != resource.ComponentID ||
				claim.Target != resource.Target {
				result.Status, result.Reason = Attention, JSONDocumentInvalid
				return result, managedFileSnapshot{}
			}
			state.claim = &claim
			break
		}
	}
	switch {
	case state.claim == nil && !target.present:
		result.Status, result.Reason = NeedsChange, ResourceMissing
	case state.claim == nil:
		result.Status, result.Reason = Ready, ResourceExists
	case !target.present:
		result.Status, result.Reason = NeedsChange, ResourceMissing
	case target.sha256 != state.claim.SHA256 || target.mode != state.claim.Mode:
		result.Status, result.Reason = NeedsChange, JSONFieldsDrifted
	default:
		result.Status, result.Reason = Ready, ResourceExists
	}
	return result, state
}

func inspectManagedTarget(
	target domain.Location,
	host Host,
) (fileSnapshot, Reason, bool) {
	reader, ok := host.(digestHost)
	if !ok {
		return fileSnapshot{}, InspectionFailed, false
	}
	entry, err := reader.InspectDigest(target)
	return classifyManagedEntry(entry, err, false)
}

func inspectManagedRegistry(
	target domain.Location,
	host Host,
	cache map[domain.Location]fileSnapshot,
) (fileSnapshot, []managedFileClaim, Reason, bool) {
	if snapshot, exists := cache[target]; exists {
		claims, err := decodeManagedRegistry(snapshot.raw)
		if err != nil {
			return fileSnapshot{}, nil, JSONDocumentInvalid, false
		}
		return snapshot, claims, "", true
	}
	entry, err := host.Inspect(target, true)
	snapshot, reason, safe := classifyManagedEntry(entry, err, true)
	if !safe {
		return fileSnapshot{}, nil, reason, false
	}
	cache[target] = snapshot
	if !snapshot.present {
		return snapshot, []managedFileClaim{}, "", true
	}
	claims, decodeErr := decodeManagedRegistry(snapshot.raw)
	if decodeErr != nil {
		return fileSnapshot{}, nil, JSONDocumentInvalid, false
	}
	return snapshot, claims, "", true
}

func classifyManagedEntry(
	entry hostfs.Entry,
	err error,
	includeContent bool,
) (fileSnapshot, Reason, bool) {
	if err != nil {
		if isMissing(err) {
			return fileSnapshot{}, "", true
		}
		return fileSnapshot{}, InspectionFailed, false
	}
	if entry.Kind == hostfs.EntrySymlink {
		return fileSnapshot{}, SymbolicLink, false
	}
	if entry.Kind != hostfs.EntryRegular {
		return fileSnapshot{}, WrongKind, false
	}
	raw := []byte(nil)
	if includeContent {
		raw = append(raw, entry.Content...)
	}
	return fileSnapshot{
		present: true, raw: raw, sha256: entry.SHA256, mode: entry.Mode,
		device: entry.Device, inode: entry.Inode,
		birthSeconds:     entry.BirthSeconds,
		birthNanoseconds: entry.BirthNanoseconds,
	}, "", true
}

func isMissing(err error) bool {
	return errors.Is(err, fs.ErrNotExist)
}

func decodeManagedRegistry(raw []byte) ([]managedFileClaim, error) {
	var registry managedFileRegistry
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&registry); err != nil {
		return nil, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return nil, fmt.Errorf("registry must contain one JSON value")
	}
	if registry.SchemaVersion != managedFileRegistrySchemaVersion ||
		registry.Claims == nil {
		return nil, fmt.Errorf("unsupported managed file registry")
	}
	for index, claim := range registry.Claims {
		if !validManagedClaim(claim) ||
			(index > 0 && managedClaimKey(registry.Claims[index-1]) >=
				managedClaimKey(claim)) {
			return nil, fmt.Errorf("invalid managed file claim")
		}
		for previous := 0; previous < index; previous++ {
			if registry.Claims[previous].ResourceID == claim.ResourceID {
				return nil, fmt.Errorf("duplicate managed file resource claim")
			}
			if locationsOverlap(registry.Claims[previous].Target, claim.Target) {
				return nil, fmt.Errorf("managed file claim targets overlap")
			}
		}
	}
	return append([]managedFileClaim(nil), registry.Claims...), nil
}

func validManagedClaim(claim managedFileClaim) bool {
	return preparedResourceIDPattern.MatchString(claim.ResourceID) &&
		preparedResourceIDPattern.MatchString(string(claim.ComponentID)) &&
		claim.Target.Valid() && claim.Target.Path.Portable() &&
		preparedDigestPattern.MatchString(claim.SHA256) &&
		claim.Mode == privateConfigurationMode
}

func managedClaimKey(claim managedFileClaim) string {
	return claim.ResourceID + "\x00" + string(claim.ComponentID) + "\x00" +
		string(claim.Target.Root) + "\x00" + string(claim.Target.Path)
}

func encodeManagedRegistry(claims []managedFileClaim) ([]byte, error) {
	sort.Slice(claims, func(left, right int) bool {
		return managedClaimKey(claims[left]) < managedClaimKey(claims[right])
	})
	if claims == nil {
		claims = []managedFileClaim{}
	}
	payload, err := json.MarshalIndent(managedFileRegistry{
		SchemaVersion: managedFileRegistrySchemaVersion,
		Claims:        claims,
	}, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(payload, '\n'), nil
}
