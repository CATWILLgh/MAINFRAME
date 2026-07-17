package mcpconfiguration

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type mcpPreparation struct {
	inspection Inspection
	after      map[domain.Location][]byte
	touched    map[domain.Location]bool
	groups     map[domain.Location]map[string]bool
	registryOf map[domain.Location]domain.Location
}

func (inspection Inspection) Prepare(
	components []domain.ComponentID,
	selections []mcpcatalog.Selection,
) (configuration.PreparedPlan, error) {
	plan, err := inspection.Plan(components, selections)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if plan.Blocking {
		return configuration.PreparedPlan{}, fmt.Errorf("MCP configuration plan is blocked")
	}
	builder := &mcpPreparation{
		inspection: inspection,
		after:      make(map[domain.Location][]byte),
		touched:    make(map[domain.Location]bool),
		groups:     make(map[domain.Location]map[string]bool),
		registryOf: make(map[domain.Location]domain.Location),
	}
	for _, intent := range plan.Intents {
		if intent.Kind == IntentReady {
			continue
		}
		projection, exists := inspection.projectionByID(intent.ProjectionID)
		if !exists {
			return configuration.PreparedPlan{}, fmt.Errorf("unknown MCP projection %q", intent.ProjectionID)
		}
		if err := builder.apply(projection, intent); err != nil {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"prepare MCP projection %q: %w",
				projection.ID,
				err,
			)
		}
	}
	transitions, err := builder.transitions()
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	return configuration.NewPreparedPlan(transitions)
}

func (inspection Inspection) projectionByID(id string) (releasecontract.MCPProjection, bool) {
	for _, projection := range inspection.projections {
		if projection.ID == id {
			return projection, true
		}
	}
	return releasecontract.MCPProjection{}, false
}

func (builder *mcpPreparation) apply(
	projection releasecontract.MCPProjection,
	intent Intent,
) error {
	if projection.TargetDocumentFormat() != releasecontract.MCPProjectionDocumentTOML ||
		projection.ComponentID != domain.ComponentCodex {
		return fmt.Errorf("exact adapter materialization is not implemented")
	}
	if intent.Kind == IntentRelinquish {
		return builder.updateRegistry(projection, "null", false)
	}
	nextConfig, err := builder.materializeCodexConfig(projection, intent)
	if err != nil {
		return err
	}
	builder.setAfter(projection.Target, nextConfig)
	if intent.Kind == IntentRemove {
		if err := builder.updateRegistry(projection, "", true); err != nil {
			return err
		}
	} else {
		owned, encodeErr := encodeCodexRegistryEntry(projection.DesiredEntry)
		if encodeErr != nil {
			return encodeErr
		}
		if err := builder.updateRegistry(projection, owned, false); err != nil {
			return err
		}
	}
	builder.addGroup(projection)
	return nil
}

func (builder *mcpPreparation) materializeCodexConfig(
	projection releasecontract.MCPProjection,
	intent Intent,
) ([]byte, error) {
	snapshot := builder.inspection.snapshots[projection.ID]
	config := builder.current(projection.Target)
	switch intent.Kind {
	case IntentAdd:
		return addCodexManagedBlock(
			config,
			projection.EntryKey,
			projection.DesiredEntry,
		)
	case IntentUpdate:
		if !snapshot.ownedMaterializable {
			return nil, fmt.Errorf("legacy Codex ownership has no managed-block provenance")
		}
		return updateCodexManagedBlock(
			config,
			projection.EntryKey,
			snapshot.ownedRaw,
			projection.DesiredEntry,
		)
	case IntentRemove:
		if !snapshot.ownedMaterializable {
			return nil, fmt.Errorf("legacy Codex ownership has no managed-block provenance")
		}
		return removeCodexManagedBlock(
			config,
			projection.EntryKey,
			snapshot.ownedRaw,
		)
	case IntentConflict, IntentUnsupported:
		return nil, fmt.Errorf("MCP intent %q cannot be materialized", intent.Kind)
	default:
		return nil, fmt.Errorf("unsupported MCP intent %q", intent.Kind)
	}
}

func (builder *mcpPreparation) updateRegistry(
	projection releasecontract.MCPProjection,
	raw string,
	remove bool,
) error {
	location := projection.RegistryTarget
	document, err := builder.registryDocument(location)
	if err != nil {
		return err
	}
	pointer, err := jsondocument.ParsePointer(
		projection.RegistryEntriesPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return err
	}
	if remove {
		document, err = document.Delete(pointer)
	} else {
		document, err = document.Set(pointer, []byte(raw))
	}
	if err != nil {
		return fmt.Errorf("materialize MCP ownership registry: %w", err)
	}
	builder.setAfter(location, document.Indented())
	builder.addGroup(projection)
	return nil
}

func (builder *mcpPreparation) registryDocument(
	location domain.Location,
) (jsondocument.Document, error) {
	raw := builder.current(location)
	if !builder.inspection.files[location].present && !builder.touched[location] {
		raw = []byte(`{"version":1,"servers":{}}`)
	}
	document, err := jsondocument.Parse(raw)
	if err != nil {
		return jsondocument.Document{}, fmt.Errorf("parse MCP ownership registry: %w", err)
	}
	return document, nil
}

func (builder *mcpPreparation) current(location domain.Location) []byte {
	if raw, exists := builder.after[location]; exists {
		return append([]byte(nil), raw...)
	}
	return append([]byte(nil), builder.inspection.files[location].raw...)
}

func (builder *mcpPreparation) setAfter(location domain.Location, raw []byte) {
	builder.after[location] = append([]byte(nil), raw...)
	builder.touched[location] = true
}

func (builder *mcpPreparation) addGroup(projection releasecontract.MCPProjection) {
	resources := builder.groups[projection.Target]
	if resources == nil {
		resources = make(map[string]bool)
		builder.groups[projection.Target] = resources
	}
	resources[projection.ID] = true
	builder.registryOf[projection.RegistryTarget] = projection.Target
}

func (builder *mcpPreparation) transitions() ([]configuration.Transition, error) {
	var result []configuration.Transition
	for configTarget, resources := range builder.groups {
		transition, err := builder.transition(configTarget, resources)
		if err != nil {
			return nil, err
		}
		if len(transition.Mutations) > 0 {
			result = append(result, transition)
		}
	}
	return result, nil
}

func (builder *mcpPreparation) transition(
	configTarget domain.Location,
	resources map[string]bool,
) (configuration.Transition, error) {
	var targets []domain.Location
	for target := range builder.touched {
		if target == configTarget || builder.registryOf[target] == configTarget {
			targets = append(targets, target)
		}
	}
	sort.Slice(targets, func(left, right int) bool {
		return mcpLocationLess(targets[left], targets[right])
	})
	var mutations []configuration.FileMutation
	for _, target := range targets {
		mutation, err := builder.mutation(target)
		if err != nil {
			return configuration.Transition{}, err
		}
		if mutation != nil {
			mutations = append(mutations, *mutation)
		}
	}
	return configuration.Transition{
		ResourceIDs: sortedMCPResourceIDs(resources),
		Mutations:   mutations,
	}, nil
}

func (builder *mcpPreparation) mutation(
	target domain.Location,
) (*configuration.FileMutation, error) {
	snapshot, exists := builder.inspection.files[target]
	if !exists || snapshot.problem != "" {
		return nil, fmt.Errorf("MCP target snapshot is unavailable")
	}
	after := builder.after[target]
	if snapshot.present && bytes.Equal(snapshot.raw, after) {
		return nil, nil
	}
	mode, err := mcpPreparedMode(snapshot)
	if err != nil {
		return nil, err
	}
	return &configuration.FileMutation{
		Target: target,
		Before: mcpBeforeImage(snapshot),
		After:  append([]byte(nil), after...),
		Mode:   mode,
	}, nil
}

func mcpBeforeImage(snapshot mcpFileSnapshot) configuration.BeforeImage {
	if !snapshot.present {
		return configuration.BeforeImage{}
	}
	digest := sha256.Sum256(snapshot.raw)
	return configuration.BeforeImage{
		Exists: true, SHA256: hex.EncodeToString(digest[:]),
		Mode: snapshot.mode, Device: snapshot.device, Inode: snapshot.inode,
	}
}

func mcpPreparedMode(snapshot mcpFileSnapshot) (uint32, error) {
	if !snapshot.present {
		return 0o600, nil
	}
	if snapshot.device == 0 || snapshot.inode == 0 || snapshot.mode&0o400 == 0 {
		return 0, fmt.Errorf("existing MCP target metadata is incomplete or unsafe")
	}
	return snapshot.mode & 0o600, nil
}

func sortedMCPResourceIDs(values map[string]bool) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func mcpLocationLess(left, right domain.Location) bool {
	if left.Root != right.Root {
		return left.Root < right.Root
	}
	return left.Path < right.Path
}
