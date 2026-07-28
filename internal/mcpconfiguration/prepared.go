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
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type mcpPreparation struct {
	inspection Inspection
	base       []configuration.Transition
	baseIndex  map[domain.Location]baseMutationReference
	baseAfter  map[domain.Location][]byte
	after      map[domain.Location][]byte
	removed    map[domain.Location]bool
	touched    map[domain.Location]bool
	groups     map[domain.Location]map[string]bool
	registryOf map[domain.Location]domain.Location
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
	if intent.Kind == IntentRelinquish {
		return builder.updateRegistry(projection, "null", false)
	}
	nextConfig, err := builder.materializeConfig(projection, intent)
	if err != nil {
		return err
	}
	builder.setAfter(projection.Target, nextConfig)
	if intent.Kind == IntentRemove {
		if err := builder.updateRegistry(projection, "", true); err != nil {
			return err
		}
	} else {
		owned, encodeErr := builder.mcpRegistryEntry(projection)
		if encodeErr != nil {
			return encodeErr
		}
		if err := builder.updateRegistry(projection, owned, false); err != nil {
			return err
		}
	}
	builder.addGroup(projection)
	if err := builder.applyPrivateCredentialFile(projection, intent); err != nil {
		return err
	}
	return nil
}

func (builder *mcpPreparation) applyPrivateCredentialFile(
	projection releasecontract.MCPProjection,
	intent Intent,
) error {
	target := projection.SecretTarget()
	if !target.Valid() {
		return nil
	}
	binding, selected := builder.inspection.credentials[projection.ID]
	if intent.Kind != IntentAdd &&
		intent.Kind != IntentUpdate &&
		intent.Kind != IntentRemove {
		return nil
	}
	snapshot := builder.inspection.files[target]
	projectionSnapshot := builder.inspection.snapshots[projection.ID]
	if snapshot.problem != "" ||
		(snapshot.present && !projectionSnapshot.privateSecretOwned) {
		return fmt.Errorf("private credential file is not safely replaceable")
	}
	if !selected || binding.ProfileID != "remote-api-key" {
		if !projectionSnapshot.privateSecretOwned {
			return nil
		}
		builder.removed[target] = true
		builder.touched[target] = true
		builder.registryOf[target] = projection.Target
		return nil
	}
	builder.setAfter(
		target,
		[]byte(configuration.DeferredSecretFilePlaceholder),
	)
	builder.registryOf[target] = projection.Target
	return nil
}

func (builder *mcpPreparation) materializeConfig(
	projection releasecontract.MCPProjection,
	intent Intent,
) ([]byte, error) {
	switch {
	case projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON &&
		projection.ComponentID == domain.ComponentAntigravity2:
		return builder.materializeJSONConfig(projection, intent)
	case projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentTOML &&
		projection.ComponentID == domain.ComponentCodex:
		return builder.materializeCodexConfig(projection, intent)
	case projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON &&
		projection.ComponentID == domain.ComponentClaudeCode:
		return builder.materializeJSONConfig(projection, intent)
	case projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON &&
		projection.ComponentID == domain.ComponentOpenCode:
		return builder.materializeJSONConfig(projection, intent)
	default:
		return nil, fmt.Errorf("exact adapter materialization is not implemented")
	}
}

func (builder *mcpPreparation) mcpRegistryEntry(
	projection releasecontract.MCPProjection,
) (string, error) {
	if projection.ComponentID == domain.ComponentAntigravity2 &&
		projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON {
		if binding, exists := builder.inspection.credentials[projection.ID]; exists {
			return encodeAntigravitySecretRegistryEntry(projection, binding)
		}
		return projection.DesiredEntry, nil
	}
	if projection.ComponentID == domain.ComponentClaudeCode &&
		projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON {
		return projection.DesiredEntry, nil
	}
	if projection.ComponentID == domain.ComponentOpenCode &&
		projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentJSON {
		if binding, exists := builder.inspection.credentials[projection.ID]; exists {
			return encodeOpenCodeSecretRegistryEntry(projection, binding)
		}
		return projection.DesiredEntry, nil
	}
	if projection.ComponentID == domain.ComponentCodex &&
		projection.TargetDocumentFormat() == releasecontract.MCPProjectionDocumentTOML {
		return encodeCodexRegistryEntry(projection.DesiredEntry)
	}
	return "", fmt.Errorf("exact MCP registry materialization is not implemented")
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
	if err := builder.rejectBaseMutation(location); err != nil {
		return err
	}
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
	if raw, exists := builder.baseAfter[location]; exists {
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
		if len(transition.Mutations) == 0 {
			continue
		}
		if builder.mergeBaseTransition(configTarget, transition) {
			continue
		}
		result = append(result, transition)
	}
	result = append(result, builder.base...)
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
	if builder.removed[target] {
		return &configuration.FileMutation{
			Disposition: configuration.MutationRemoveManagedSecret,
			Target:      target,
			Before:      mcpBeforeImage(snapshot),
		}, nil
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
		Disposition: configuration.MutationPresent,
		Target:      target,
		Before:      mcpBeforeImage(snapshot),
		After: configuration.AfterImage{
			Exists:  true,
			Content: append([]byte(nil), after...),
			Mode:    mode,
		},
	}, nil
}

func mcpBeforeImage(snapshot mcpFileSnapshot) configuration.BeforeImage {
	if !snapshot.present {
		return configuration.BeforeImage{}
	}
	digest := snapshot.sha256
	if digest == "" {
		sum := sha256.Sum256(snapshot.raw)
		digest = hex.EncodeToString(sum[:])
	}
	return configuration.BeforeImage{
		Exists: true, SHA256: digest,
		Mode: snapshot.mode, Device: snapshot.device, Inode: snapshot.inode,
		BirthSeconds:     snapshot.birthSeconds,
		BirthNanoseconds: snapshot.birthNanoseconds,
	}
}

func mcpPreparedMode(snapshot mcpFileSnapshot) (uint32, error) {
	if !snapshot.present {
		return 0o600, nil
	}
	if snapshot.device == 0 || snapshot.inode == 0 ||
		snapshot.birthSeconds <= 0 ||
		snapshot.birthNanoseconds < 0 ||
		snapshot.birthNanoseconds >= 1_000_000_000 ||
		snapshot.mode&0o400 == 0 {
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
