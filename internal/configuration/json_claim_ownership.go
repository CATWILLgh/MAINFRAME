package configuration

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type jsonClaimSnapshot struct {
	config   jsonSnapshot
	registry jsonSnapshot
}

type claimRegistry struct {
	SchemaVersion     int                   `json:"schema_version"`
	TargetPreexisting *bool                 `json:"target_preexisting"`
	CreatedPointers   []string              `json:"created_pointers"`
	Claims            map[string]claimState `json:"claims"`
}

type claimState struct {
	State          string          `json:"state"`
	Kind           string          `json:"kind"`
	Pointer        string          `json:"pointer"`
	Owned          json.RawMessage `json:"owned,omitempty"`
	Selector       *claimSelector  `json:"selector,omitempty"`
	Predecessor    json.RawMessage `json:"predecessor,omitempty"`
	PredecessorSet *bool           `json:"predecessor_present,omitempty"`
}

type claimSelector struct {
	Pointer string          `json:"pointer"`
	Value   json.RawMessage `json:"value"`
}

type claimReconciliation struct {
	config          jsondocument.Document
	registry        claimRegistry
	configChanged   bool
	registryChanged bool
	removeConfig    bool
	removeRegistry  bool
}

func observeJSONClaimResource(
	resource releasecontract.Resource,
	host Host,
	snapshots map[domain.Location]jsonSnapshot,
) (Observation, jsonClaimSnapshot) {
	result := Observation{ResourceID: resource.ID, ComponentID: resource.ComponentID}
	state := jsonClaimSnapshot{
		config:   jsonSnapshotFor(resource.Target, host, snapshots),
		registry: jsonSnapshotFor(resource.JSONClaimOwnership.RegistryTarget, host, snapshots),
	}
	for _, snapshot := range []jsonSnapshot{state.config, state.registry} {
		if reason, unsafe := unsafeOwnedSnapshot(snapshot); unsafe {
			result.Status, result.Reason = Attention, reason
			return result, state
		}
	}
	reconciliation, err := reconcileJSONClaims(resource.JSONClaimOwnership, state, true)
	if err != nil {
		result.Status, result.Reason = Attention, JSONDocumentInvalid
		return result, state
	}
	if !reconciliation.configChanged && !reconciliation.registryChanged {
		result.Status, result.Reason = Ready, JSONFieldsMatch
	} else {
		result.Status, result.Reason = NeedsChange, JSONFieldsDrifted
	}
	return result, state
}

func reconcileJSONClaims(
	ownership *releasecontract.JSONClaimOwnership,
	snapshot jsonClaimSnapshot,
	selected bool,
) (claimReconciliation, error) {
	config, err := claimDocument(snapshot.config)
	if err != nil {
		return claimReconciliation{}, err
	}
	registry, err := readClaimRegistry(snapshot.registry)
	if err != nil {
		return claimReconciliation{}, err
	}
	if !snapshot.registryPresent() && !selected {
		return claimReconciliation{config: config, registry: registry}, nil
	}
	if !snapshot.registryPresent() {
		registry.TargetPreexisting = boolPointer(snapshot.configPresent())
	}
	beforeConfig := config.Canonical()
	beforeRegistry, _ := json.Marshal(registry)
	var pruneCandidates []string
	config, pruneCandidates, err = reconcileRetiredClaims(
		config, &registry, ownership, selected,
	)
	if err != nil {
		return claimReconciliation{}, err
	}
	for _, claim := range ownership.Claims {
		if !selected {
			continue
		}
		state, tracked := registry.Claims[claim.ID]
		if !tracked {
			registry.CreatedPointers = mergeCreatedPointers(
				registry.CreatedPointers,
				missingClaimPointers(config, claim.Pointer),
			)
		}
		config, registry.Claims[claim.ID], err = selectJSONClaim(config, claim, state, tracked)
		if err != nil {
			return claimReconciliation{}, err
		}
	}
	config, _, err = pruneCreatedPointers(config, pruneCandidates)
	if err != nil {
		return claimReconciliation{}, err
	}
	afterRegistry, _ := json.Marshal(registry)
	removeConfig, removeRegistry := claimRemovalFlags(config, registry, snapshot)
	return claimReconciliation{
		config: config, registry: registry,
		configChanged: beforeConfig != config.Canonical(),
		registryChanged: !bytes.Equal(beforeRegistry, afterRegistry) ||
			!snapshot.registryPresent(),
		removeConfig: removeConfig, removeRegistry: removeRegistry,
	}, nil
}

func claimRemovalFlags(
	config jsondocument.Document,
	registry claimRegistry,
	snapshot jsonClaimSnapshot,
) (bool, bool) {
	removeRegistry := snapshot.registryPresent() && len(registry.Claims) == 0
	removeConfig := removeRegistry && registry.TargetPreexisting != nil &&
		!*registry.TargetPreexisting && config.Canonical() == `{}`
	return removeConfig, removeRegistry
}

func claimFromState(identifier string, state claimState) (releasecontract.JSONClaim, error) {
	if !preparedResourceIDPattern.MatchString(identifier) {
		return releasecontract.JSONClaim{}, fmt.Errorf("registry contains invalid retired claim id %q", identifier)
	}
	claim := releasecontract.JSONClaim{
		ID: identifier, Kind: releasecontract.JSONClaimKind(state.Kind),
		Pointer: state.Pointer, Desired: string(state.Owned),
	}
	if state.Selector != nil {
		claim.SelectorPointer = state.Selector.Pointer
		claim.SelectorValue = string(state.Selector.Value)
	}
	if !stateMatchesClaim(state, claim) {
		return releasecontract.JSONClaim{}, fmt.Errorf("registry contains invalid retired claim %q", identifier)
	}
	if _, err := jsondocument.ParsePointer(claim.Pointer); err != nil {
		return releasecontract.JSONClaim{}, fmt.Errorf("registry retired claim %q: %w", identifier, err)
	}
	return claim, nil
}

func selectJSONClaim(
	document jsondocument.Document,
	claim releasecontract.JSONClaim,
	state claimState,
	tracked bool,
) (jsondocument.Document, claimState, error) {
	if tracked && !stateMatchesClaim(state, claim) {
		return document, claimState{}, fmt.Errorf("registry claim metadata mismatch")
	}
	if tracked && state.State == "relinquished" {
		return document, state, nil
	}
	if claim.Kind == releasecontract.JSONClaimExactScalar {
		return selectScalarClaim(document, claim, state, tracked)
	}
	return selectArrayClaim(document, claim, state, tracked)
}

func selectScalarClaim(
	document jsondocument.Document,
	claim releasecontract.JSONClaim,
	state claimState,
	tracked bool,
) (jsondocument.Document, claimState, error) {
	actual, present, err := claimValue(document, claim.Pointer)
	if err != nil {
		return document, claimState{}, err
	}
	if tracked && (state.State != "owned" || !present || !sameJSON(actual, state.Owned)) {
		return document, relinquishedState(claim), nil
	}
	if !tracked {
		state = ownedState(claim)
		state.PredecessorSet = boolPointer(present)
		if present {
			state.Predecessor = cloneRaw(actual)
		}
	}
	updated, err := setClaimValue(document, claim.Pointer, []byte(claim.Desired))
	if err != nil {
		return document, claimState{}, err
	}
	state.Owned = json.RawMessage(claim.Desired)
	return updated, state, nil
}

func selectArrayClaim(
	document jsondocument.Document,
	claim releasecontract.JSONClaim,
	state claimState,
	tracked bool,
) (jsondocument.Document, claimState, error) {
	entries, err := claimArray(document, claim.Pointer)
	if err != nil {
		return document, claimState{}, err
	}
	matches := matchingEntries(entries, claim)
	if tracked {
		if state.State != "owned" || len(matches) != 1 || !sameJSON(entries[matches[0]], state.Owned) {
			return document, relinquishedState(claim), nil
		}
		entries[matches[0]] = json.RawMessage(claim.Desired)
	} else {
		if len(matches) != 0 {
			return document, relinquishedState(claim), nil
		}
		entries = append(entries, json.RawMessage(claim.Desired))
		state = ownedState(claim)
	}
	state.Owned = json.RawMessage(claim.Desired)
	updated, err := setClaimValue(document, claim.Pointer, marshalRawArray(entries))
	return updated, state, err
}

func deselectJSONClaim(
	document jsondocument.Document,
	claim releasecontract.JSONClaim,
	state claimState,
) (jsondocument.Document, bool, error) {
	if !stateMatchesClaim(state, claim) || state.State == "relinquished" {
		return document, false, nil
	}
	if claim.Kind == releasecontract.JSONClaimExactScalar {
		actual, present, err := claimValue(document, claim.Pointer)
		if err != nil || !present || !sameJSON(actual, state.Owned) {
			return document, false, err
		}
		if state.PredecessorSet == nil {
			return document, false, fmt.Errorf("scalar predecessor state is absent")
		}
		if *state.PredecessorSet {
			updated, err := setClaimValue(document, claim.Pointer, state.Predecessor)
			return updated, false, err
		}
		pointer, _ := jsondocument.ParsePointer(claim.Pointer)
		updated, err := document.Delete(pointer)
		return updated, true, err
	}
	entries, err := claimArray(document, claim.Pointer)
	if err != nil {
		return document, false, err
	}
	matches := matchingEntries(entries, claim)
	if len(matches) != 1 || !sameJSON(entries[matches[0]], state.Owned) {
		return document, false, nil
	}
	index := matches[0]
	entries = append(entries[:index], entries[index+1:]...)
	updated, err := setClaimValue(document, claim.Pointer, marshalRawArray(entries))
	return updated, true, err
}

func claimDocument(snapshot jsonSnapshot) (jsondocument.Document, error) {
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		return jsondocument.Parse([]byte(`{}`))
	}
	return snapshot.document, snapshot.parseErr
}

func readClaimRegistry(snapshot jsonSnapshot) (claimRegistry, error) {
	if errors.Is(snapshot.err, fs.ErrNotExist) {
		return claimRegistry{
			SchemaVersion: 1, CreatedPointers: []string{},
			Claims: map[string]claimState{},
		}, nil
	}
	var registry claimRegistry
	if err := decodeStrictConfiguration(snapshot.document.Raw(), &registry); err != nil ||
		registry.SchemaVersion != 1 || registry.TargetPreexisting == nil ||
		registry.CreatedPointers == nil || registry.Claims == nil ||
		!validCreatedPointers(registry.CreatedPointers) ||
		!createdPointersMatchClaims(registry.CreatedPointers, registry.Claims) {
		return claimRegistry{}, fmt.Errorf("invalid JSON claim registry")
	}
	return registry, nil
}

func decodeStrictConfiguration(payload []byte, target any) error {
	if _, err := jsondocument.Parse(payload); err != nil {
		return err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func stateMatchesClaim(state claimState, claim releasecontract.JSONClaim) bool {
	if state.Kind != string(claim.Kind) || state.Pointer != claim.Pointer ||
		(state.State != "owned" && state.State != "relinquished") {
		return false
	}
	if state.State == "relinquished" &&
		(len(state.Owned) != 0 || len(state.Predecessor) != 0 || state.PredecessorSet != nil) {
		return false
	}
	if state.State == "owned" &&
		(len(state.Owned) == 0 || !validJSONRaw(state.Owned)) {
		return false
	}
	if claim.Kind == releasecontract.JSONClaimExactScalar {
		return state.Selector == nil &&
			(state.State == "relinquished" ||
				(state.PredecessorSet != nil &&
					((*state.PredecessorSet && validJSONRaw(state.Predecessor)) ||
						(!*state.PredecessorSet && len(state.Predecessor) == 0))))
	}
	return state.PredecessorSet == nil && len(state.Predecessor) == 0 &&
		state.Selector != nil && state.Selector.Pointer == claim.SelectorPointer &&
		sameJSON(state.Selector.Value, json.RawMessage(claim.SelectorValue))
}

func validJSONRaw(raw json.RawMessage) bool {
	_, err := jsondocument.Parse(raw)
	return err == nil
}

func ownedState(claim releasecontract.JSONClaim) claimState {
	state := claimState{State: "owned", Kind: string(claim.Kind), Pointer: claim.Pointer}
	if claim.Kind == releasecontract.JSONClaimArrayEntry {
		state.Selector = &claimSelector{
			Pointer: claim.SelectorPointer, Value: json.RawMessage(claim.SelectorValue),
		}
	}
	return state
}

func relinquishedState(claim releasecontract.JSONClaim) claimState {
	state := ownedState(claim)
	state.State = "relinquished"
	return state
}

func (snapshot jsonClaimSnapshot) registryPresent() bool {
	return !errors.Is(snapshot.registry.err, fs.ErrNotExist)
}

func (snapshot jsonClaimSnapshot) configPresent() bool {
	return !errors.Is(snapshot.config.err, fs.ErrNotExist)
}
