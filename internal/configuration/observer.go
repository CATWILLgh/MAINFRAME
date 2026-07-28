package configuration

import (
	"errors"
	"fmt"
	"io/fs"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type Status string

const (
	Ready         Status = "ready"
	NeedsChange   Status = "needs_change"
	NotApplicable Status = "not_applicable"
	Attention     Status = "attention"
	NotAssessed   Status = "not_assessed"
)

type Reason string

const (
	ResourceExists           Reason = "resource_exists"
	DirectoryExists          Reason = "directory_exists"
	LinePresent              Reason = "line_present"
	ResourceMissing          Reason = "resource_missing"
	DirectoryMissing         Reason = "directory_missing"
	LineMissing              Reason = "line_missing"
	OptionalTargetMissing    Reason = "optional_target_missing"
	SymbolicLink             Reason = "symbolic_link"
	WrongKind                Reason = "wrong_kind"
	InspectionFailed         Reason = "inspection_failed"
	ObservationUnsupported   Reason = "observation_unsupported"
	JSONFieldsMatch          Reason = "json_fields_match"
	JSONFieldsDrifted        Reason = "json_fields_drifted"
	JSONDocumentInvalid      Reason = "json_document_invalid"
	ExternalStateSatisfied   Reason = "external_state_satisfied"
	ManualActionRequired     Reason = "manual_action_required"
	ManualActionUnverified   Reason = "manual_action_unverified"
	ExternalStateUnavailable Reason = "external_state_unavailable"
	ExternalInspectionFailed Reason = "external_inspection_failed"
)

type Observation struct {
	ResourceID  string
	ComponentID domain.ComponentID
	Status      Status
	Reason      Reason
}

type Host interface {
	Inspect(location domain.Location, includeContent bool) (hostfs.Entry, error)
}

type ExternalStatus string

const (
	ExternalSatisfied      ExternalStatus = "satisfied"
	ExternalActionRequired ExternalStatus = "action_required"
	ExternalUnavailable    ExternalStatus = "unavailable"
	ExternalFailed         ExternalStatus = "failed"
)

type ExternalObservation struct {
	Status ExternalStatus
}

type ExternalObserver interface {
	Observe(releasecontract.Resource) ExternalObservation
}

func Observe(resources []releasecontract.Resource, host Host) ([]Observation, error) {
	inspection, err := Inspect(resources, host)
	if err != nil {
		return nil, err
	}
	return inspection.Observations(), nil
}

func Validate(resources []releasecontract.Resource, observations []Observation) error {
	if err := validateResourceSet(resources); err != nil {
		return err
	}
	resourceByID := make(map[string]releasecontract.Resource, len(resources))
	for _, resource := range resources {
		resourceByID[resource.ID] = resource
	}
	seen := make(map[string]bool, len(observations))
	for _, observation := range observations {
		resource, exists := resourceByID[observation.ResourceID]
		if !exists {
			return fmt.Errorf("configuration observation references unknown resource %q", observation.ResourceID)
		}
		if seen[observation.ResourceID] {
			return fmt.Errorf("duplicate configuration observation %q", observation.ResourceID)
		}
		seen[observation.ResourceID] = true
		if observation.ComponentID != resource.ComponentID {
			return fmt.Errorf("configuration observation %q has component mismatch", observation.ResourceID)
		}
		if !validObservation(resource, observation) {
			return fmt.Errorf("configuration observation %q has impossible status and reason", observation.ResourceID)
		}
	}
	if len(seen) != len(resourceByID) {
		return fmt.Errorf("configuration observations do not cover every resource")
	}
	return nil
}

func observeResource(
	resource releasecontract.Resource,
	host Host,
	jsonSnapshots map[domain.Location]jsonSnapshot,
	files map[domain.Location]fileSnapshot,
	external ExternalObserver,
) (Observation, error) {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	if resource.Observation == releasecontract.SupportUnimplemented {
		result.Status, result.Reason = NotAssessed, ObservationUnsupported
		return result, nil
	}
	if resource.Observation != releasecontract.SupportSupported || !supportedStrategy(resource.Strategy) {
		if resource.Strategy != releasecontract.StrategyManualAction ||
			resource.ExternalState == nil {
			return Observation{}, fmt.Errorf("invalid observation support for strategy %q", resource.Strategy)
		}
		return observeExternalResource(resource, external)
	}
	if resource.Strategy == releasecontract.StrategyJSONKeyMerge {
		return observeJSONResource(resource, host, jsonSnapshots), nil
	}
	if resource.Strategy == releasecontract.StrategyExactJSONDocument {
		return observeExactJSONDocument(resource, host, jsonSnapshots), nil
	}
	readContent := resource.Strategy == releasecontract.StrategyShellLine ||
		resource.Strategy == releasecontract.StrategyShellLineIfPresent
	if readContent && resource.DesiredLine == "" {
		return Observation{}, fmt.Errorf("supported shell observation has no desired line")
	}
	entry, err := host.Inspect(resource.Target, readContent)
	if errors.Is(err, fs.ErrNotExist) {
		files[resource.Target] = fileSnapshot{}
		result.Status, result.Reason = missingStatus(resource.Strategy)
		return result, nil
	}
	if err != nil {
		result.Status, result.Reason = Attention, InspectionFailed
		return result, nil
	}
	if entry.Kind == hostfs.EntrySymlink {
		result.Status, result.Reason = Attention, SymbolicLink
		return result, nil
	}
	if entry.Kind == hostfs.EntryRegular {
		files[resource.Target] = fileSnapshot{
			present:          true,
			raw:              append([]byte(nil), entry.Content...),
			mode:             entry.Mode,
			device:           entry.Device,
			inode:            entry.Inode,
			birthSeconds:     entry.BirthSeconds,
			birthNanoseconds: entry.BirthNanoseconds,
		}
	}
	return classifyExisting(resource, entry, result), nil
}

func observeExactJSONDocument(
	resource releasecontract.Resource,
	host Host,
	snapshots map[domain.Location]jsonSnapshot,
) Observation {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	snapshot := jsonSnapshotFor(resource.Target, host, snapshots)
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		result.Status, result.Reason = NeedsChange, ResourceMissing
		return result
	}
	if snapshot.err != nil {
		result.Status, result.Reason = Attention, InspectionFailed
		return result
	}
	if snapshot.entry.Kind == hostfs.EntrySymlink {
		result.Status, result.Reason = Attention, SymbolicLink
		return result
	}
	if snapshot.entry.Kind != hostfs.EntryRegular {
		result.Status, result.Reason = Attention, WrongKind
		return result
	}
	if snapshot.parseErr != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	if _, err := resource.ValidateExactJSONDocument(snapshot.entry.Content); err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	if snapshot.document.Canonical() == resource.ExactJSONExemplar &&
		snapshot.entry.Mode == privateConfigurationMode {
		result.Status, result.Reason = Ready, JSONFieldsMatch
		return result
	}
	result.Status, result.Reason = NeedsChange, JSONFieldsDrifted
	return result
}

func observeExternalResource(
	resource releasecontract.Resource,
	external ExternalObserver,
) (Observation, error) {
	result := Observation{
		ResourceID:  resource.ID,
		ComponentID: resource.ComponentID,
	}
	if external == nil {
		result.Status, result.Reason = NotAssessed, ExternalStateUnavailable
		return result, nil
	}
	switch external.Observe(resource).Status {
	case ExternalSatisfied:
		result.Status, result.Reason = Ready, ExternalStateSatisfied
	case ExternalActionRequired:
		result.Status, result.Reason = NeedsChange, ManualActionRequired
	case ExternalUnavailable:
		result.Status, result.Reason = NotAssessed, ExternalStateUnavailable
	case ExternalFailed:
		result.Status, result.Reason = Attention, ExternalInspectionFailed
	default:
		return Observation{}, fmt.Errorf("external observer returned invalid status")
	}
	return result, nil
}

type jsonSnapshot struct {
	entry    hostfs.Entry
	err      error
	document jsondocument.Document
	parseErr error
}

func observeJSONResource(
	resource releasecontract.Resource,
	host Host,
	snapshots map[domain.Location]jsonSnapshot,
) Observation {
	if resource.JSONMapOwnership != nil {
		return observeOwnedJSONMap(resource, host, snapshots)
	}
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	snapshot := jsonSnapshotFor(resource.Target, host, snapshots)
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		result.Status, result.Reason = NeedsChange, ResourceMissing
		return result
	}
	if snapshot.err != nil {
		result.Status, result.Reason = Attention, InspectionFailed
		return result
	}
	if snapshot.entry.Kind == hostfs.EntrySymlink {
		result.Status, result.Reason = Attention, SymbolicLink
		return result
	}
	if snapshot.entry.Kind != hostfs.EntryRegular {
		result.Status, result.Reason = Attention, WrongKind
		return result
	}
	if snapshot.parseErr != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result
	}
	return compareJSONFields(resource, snapshot.document, result)
}

func jsonSnapshotFor(
	location domain.Location,
	host Host,
	snapshots map[domain.Location]jsonSnapshot,
) jsonSnapshot {
	snapshot, exists := snapshots[location]
	if !exists {
		entry, err := host.Inspect(location, true)
		entry.Content = append([]byte(nil), entry.Content...)
		snapshot = jsonSnapshot{entry: entry, err: err}
		if err == nil && entry.Kind == hostfs.EntryRegular {
			snapshot.document, snapshot.parseErr = jsondocument.Parse(entry.Content)
		}
		snapshots[location] = snapshot
	}
	return snapshot
}

func compareJSONFields(
	resource releasecontract.Resource,
	document jsondocument.Document,
	result Observation,
) Observation {
	for _, field := range resource.OwnedJSONFields {
		pointer, err := jsondocument.ParsePointer(field.Pointer)
		if err != nil {
			result.Status, result.Reason = Attention, JSONDocumentInvalid
			return result
		}
		actual, status := document.Lookup(pointer)
		if status == jsondocument.Incompatible {
			result.Status, result.Reason = Attention, JSONDocumentInvalid
			return result
		}
		if status == jsondocument.Missing || actual != field.Desired {
			result.Status, result.Reason = NeedsChange, JSONFieldsDrifted
			return result
		}
	}
	result.Status, result.Reason = Ready, JSONFieldsMatch
	return result
}

func classifyExisting(
	resource releasecontract.Resource,
	entry hostfs.Entry,
	result Observation,
) Observation {
	switch resource.Strategy {
	case releasecontract.StrategySeedIfAbsent:
		if entry.Kind == hostfs.EntryRegular {
			result.Status, result.Reason = Ready, ResourceExists
		} else {
			result.Status, result.Reason = Attention, WrongKind
		}
	case releasecontract.StrategyEnsureDir:
		if entry.Kind == hostfs.EntryDirectory {
			result.Status, result.Reason = Ready, DirectoryExists
		} else {
			result.Status, result.Reason = Attention, WrongKind
		}
	case releasecontract.StrategyShellLine, releasecontract.StrategyShellLineIfPresent:
		if entry.Kind != hostfs.EntryRegular {
			result.Status, result.Reason = Attention, WrongKind
		} else if containsLine(entry.Content, resource.DesiredLine) {
			result.Status, result.Reason = Ready, LinePresent
		} else {
			result.Status, result.Reason = NeedsChange, LineMissing
		}
	}
	return result
}

func missingStatus(strategy releasecontract.ResourceStrategy) (Status, Reason) {
	switch strategy {
	case releasecontract.StrategyEnsureDir:
		return NeedsChange, DirectoryMissing
	case releasecontract.StrategyShellLineIfPresent:
		return NotApplicable, OptionalTargetMissing
	case releasecontract.StrategyShellLine:
		return NeedsChange, LineMissing
	default:
		return NeedsChange, ResourceMissing
	}
}

func containsLine(content []byte, desired string) bool {
	for _, line := range strings.Split(string(content), "\n") {
		if line == desired {
			return true
		}
	}
	return false
}
