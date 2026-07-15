package configuration

import (
	"errors"
	"fmt"
	"io/fs"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
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
	ResourceExists         Reason = "resource_exists"
	DirectoryExists        Reason = "directory_exists"
	LinePresent            Reason = "line_present"
	ResourceMissing        Reason = "resource_missing"
	DirectoryMissing       Reason = "directory_missing"
	LineMissing            Reason = "line_missing"
	OptionalTargetMissing  Reason = "optional_target_missing"
	SymbolicLink           Reason = "symbolic_link"
	WrongKind              Reason = "wrong_kind"
	InspectionFailed       Reason = "inspection_failed"
	ObservationUnsupported Reason = "observation_unsupported"
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

func Observe(resources []releasecontract.Resource, host Host) ([]Observation, error) {
	if host == nil {
		return nil, fmt.Errorf("host must not be nil")
	}
	seen := make(map[string]bool, len(resources))
	observations := make([]Observation, 0, len(resources))
	for _, resource := range resources {
		if resource.ID == "" || seen[resource.ID] {
			return nil, fmt.Errorf("invalid duplicate configuration resource %q", resource.ID)
		}
		if err := validateResource(resource); err != nil {
			return nil, fmt.Errorf("invalid configuration resource %q: %w", resource.ID, err)
		}
		seen[resource.ID] = true
		observation, err := observeResource(resource, host)
		if err != nil {
			return nil, fmt.Errorf("observe configuration resource %q: %w", resource.ID, err)
		}
		observations = append(observations, observation)
	}
	if err := Validate(resources, observations); err != nil {
		return nil, err
	}
	return observations, nil
}

func Validate(resources []releasecontract.Resource, observations []Observation) error {
	resourceByID := make(map[string]releasecontract.Resource, len(resources))
	for _, resource := range resources {
		if resource.ID == "" || resourceByID[resource.ID].ID != "" {
			return fmt.Errorf("invalid duplicate configuration resource %q", resource.ID)
		}
		if err := validateResource(resource); err != nil {
			return fmt.Errorf("invalid configuration resource %q: %w", resource.ID, err)
		}
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

func observeResource(resource releasecontract.Resource, host Host) (Observation, error) {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	if resource.Observation == releasecontract.SupportUnimplemented {
		result.Status, result.Reason = NotAssessed, ObservationUnsupported
		return result, nil
	}
	if resource.Observation != releasecontract.SupportSupported || !supportedStrategy(resource.Strategy) {
		return Observation{}, fmt.Errorf("invalid observation support for strategy %q", resource.Strategy)
	}
	readContent := resource.Strategy == releasecontract.StrategyShellLine ||
		resource.Strategy == releasecontract.StrategyShellLineIfPresent
	if readContent && resource.DesiredLine == "" {
		return Observation{}, fmt.Errorf("supported shell observation has no desired line")
	}
	entry, err := host.Inspect(resource.Target, readContent)
	if errors.Is(err, fs.ErrNotExist) {
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
	return classifyExisting(resource, entry, result), nil
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

func supportedStrategy(strategy releasecontract.ResourceStrategy) bool {
	switch strategy {
	case releasecontract.StrategySeedIfAbsent,
		releasecontract.StrategyEnsureDir,
		releasecontract.StrategyShellLine,
		releasecontract.StrategyShellLineIfPresent:
		return true
	default:
		return false
	}
}

func validateResource(resource releasecontract.Resource) error {
	if resource.Apply != releasecontract.SupportUnimplemented {
		return fmt.Errorf("apply support must remain unimplemented")
	}
	if resource.Observation == releasecontract.SupportUnimplemented {
		return nil
	}
	if resource.Observation != releasecontract.SupportSupported || !supportedStrategy(resource.Strategy) {
		return fmt.Errorf("invalid observation support for strategy %q", resource.Strategy)
	}
	if (resource.Strategy == releasecontract.StrategyShellLine ||
		resource.Strategy == releasecontract.StrategyShellLineIfPresent) && resource.DesiredLine == "" {
		return fmt.Errorf("supported shell observation has no desired line")
	}
	return nil
}

func validObservation(resource releasecontract.Resource, observation Observation) bool {
	if resource.Observation == releasecontract.SupportUnimplemented {
		return observation.Status == NotAssessed && observation.Reason == ObservationUnsupported
	}
	valid := map[Status]map[Reason]bool{
		Ready: {
			ResourceExists: true, DirectoryExists: true, LinePresent: true,
		},
		NeedsChange: {
			ResourceMissing: true, DirectoryMissing: true, LineMissing: true,
		},
		NotApplicable: {OptionalTargetMissing: true},
		Attention: {
			SymbolicLink: true, WrongKind: true, InspectionFailed: true,
		},
	}
	if !valid[observation.Status][observation.Reason] {
		return false
	}
	switch resource.Strategy {
	case releasecontract.StrategySeedIfAbsent:
		return observation.Reason == ResourceExists || observation.Reason == ResourceMissing ||
			observation.Reason == SymbolicLink || observation.Reason == WrongKind || observation.Reason == InspectionFailed
	case releasecontract.StrategyEnsureDir:
		return observation.Reason == DirectoryExists || observation.Reason == DirectoryMissing ||
			observation.Reason == SymbolicLink || observation.Reason == WrongKind || observation.Reason == InspectionFailed
	case releasecontract.StrategyShellLine:
		return observation.Reason == LinePresent || observation.Reason == LineMissing ||
			observation.Reason == SymbolicLink || observation.Reason == WrongKind || observation.Reason == InspectionFailed
	case releasecontract.StrategyShellLineIfPresent:
		return observation.Reason == LinePresent || observation.Reason == LineMissing ||
			observation.Reason == OptionalTargetMissing || observation.Reason == SymbolicLink ||
			observation.Reason == WrongKind || observation.Reason == InspectionFailed
	default:
		return false
	}
}
