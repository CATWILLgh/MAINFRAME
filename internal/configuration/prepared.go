package configuration

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const privateConfigurationMode uint32 = 0o600

type BeforeImage struct {
	Exists           bool
	SHA256           string
	Mode             uint32
	Device           uint64
	Inode            uint64
	BirthSeconds     int64
	BirthNanoseconds int64
}

type AfterImage struct {
	Exists  bool
	Content []byte
	Mode    uint32
}

type MutationDisposition string

const (
	MutationPresent             MutationDisposition = "present"
	MutationRemoveExactDocument MutationDisposition = "remove_exact_document"
)

type FileMutation struct {
	Disposition MutationDisposition
	Target      domain.Location
	Before      BeforeImage
	After       AfterImage
}

type Transition struct {
	ResourceIDs []string
	Mutations   []FileMutation
}

type ReadPreconditionKind string

const ReadPreconditionSymlink ReadPreconditionKind = "symlink"

type ReadPrecondition struct {
	Kind               ReadPreconditionKind
	Target             domain.Location
	Device             uint64
	Inode              uint64
	BirthSeconds       int64
	BirthNanoseconds   int64
	ExpectedTargetPath string
}

func (inspection Inspection) Prepare(
	included []domain.ComponentID,
) (PreparedPlan, error) {
	return inspection.PrepareWithPreservation(included, nil)
}

func (inspection Inspection) PrepareWithPreservation(
	included []domain.ComponentID,
	preserved []domain.ComponentID,
) (PreparedPlan, error) {
	semantic, err := inspection.PlanWithPreservation(included, preserved)
	if err != nil {
		return PreparedPlan{}, err
	}
	if len(semantic.Issues) > 0 {
		return PreparedPlan{}, fmt.Errorf(
			"configuration plan has %d unresolved issue(s)",
			len(semantic.Issues),
		)
	}
	changed := changedResourceIDs(semantic.Changes)
	if len(changed) == 0 {
		return PreparedPlan{}, nil
	}
	resources, err := changedOwnedResources(inspection.resources, changed)
	if err != nil {
		return PreparedPlan{}, err
	}
	builder := newPreparationBuilder(inspection.files)
	selected := selectedComponents(included)
	for _, resource := range resources {
		if err := builder.applyOwnedMap(
			resource,
			inspection.ownedMaps[resource.ID],
			selected[resource.ComponentID],
		); err != nil {
			return PreparedPlan{}, fmt.Errorf(
				"prepare configuration resource %q: %w",
				resource.ID,
				err,
			)
		}
	}
	transitions, err := builder.transitions()
	if err != nil {
		return PreparedPlan{}, err
	}
	return NewPreparedPlan(transitions)
}

func changedResourceIDs(changes []Change) map[string]bool {
	result := make(map[string]bool, len(changes))
	for _, change := range changes {
		result[change.ResourceID] = true
	}
	return result
}

func changedOwnedResources(
	resources []releasecontract.Resource,
	changed map[string]bool,
) ([]releasecontract.Resource, error) {
	var result []releasecontract.Resource
	for _, resource := range resources {
		if !changed[resource.ID] {
			continue
		}
		if !resource.SupportsApply() {
			return nil, fmt.Errorf(
				"configuration resource %q does not support apply",
				resource.ID,
			)
		}
		if resource.JSONMapOwnership == nil {
			return nil, fmt.Errorf(
				"configuration resource %q cannot be materialized",
				resource.ID,
			)
		}
		result = append(result, resource)
	}
	sort.Slice(result, func(left, right int) bool {
		return result[left].ID < result[right].ID
	})
	if len(result) != len(changed) {
		return nil, fmt.Errorf("configuration plan references an unknown resource")
	}
	return result, nil
}

func selectedComponents(
	included []domain.ComponentID,
) map[domain.ComponentID]bool {
	result := make(map[domain.ComponentID]bool, len(included))
	for _, component := range included {
		result[component] = true
	}
	return result
}

func cloneFileMutations(source []FileMutation) []FileMutation {
	result := make([]FileMutation, len(source))
	for index, mutation := range source {
		result[index] = mutation
		result[index].After.Content = append(
			[]byte(nil),
			mutation.After.Content...,
		)
	}
	return result
}

type preparationBuilder struct {
	files         map[domain.Location]fileSnapshot
	docs          map[domain.Location]jsondocument.Document
	groups        map[domain.Location]map[string]bool
	groupByTarget map[domain.Location]domain.Location
	touch         map[domain.Location]bool
}

func newPreparationBuilder(
	files map[domain.Location]fileSnapshot,
) *preparationBuilder {
	return &preparationBuilder{
		files: files, docs: make(map[domain.Location]jsondocument.Document),
		groups:        make(map[domain.Location]map[string]bool),
		groupByTarget: make(map[domain.Location]domain.Location),
		touch:         make(map[domain.Location]bool),
	}
}

func (builder *preparationBuilder) document(
	target domain.Location,
) (jsondocument.Document, error) {
	if document, exists := builder.docs[target]; exists {
		return document, nil
	}
	snapshot, exists := builder.files[target]
	if !exists {
		return jsondocument.Document{}, fmt.Errorf("target snapshot is unavailable")
	}
	raw := snapshot.raw
	if !snapshot.present {
		raw = []byte(`{}`)
	}
	document, err := jsondocument.Parse(raw)
	if err != nil {
		return jsondocument.Document{}, err
	}
	builder.docs[target] = document
	return document, nil
}

func (builder *preparationBuilder) set(
	target domain.Location,
	pointer string,
	raw string,
) error {
	document, err := builder.document(target)
	if err != nil {
		return err
	}
	parsed, err := jsondocument.ParsePointer(pointer)
	if err != nil {
		return err
	}
	updated, err := document.Set(parsed, []byte(raw))
	if err != nil {
		return err
	}
	builder.docs[target] = updated
	builder.touch[target] = true
	return nil
}

func (builder *preparationBuilder) transitions() ([]Transition, error) {
	var result []Transition
	for target, resources := range builder.groups {
		transition, err := builder.transition(target, resources)
		if err != nil {
			return nil, err
		}
		if len(transition.Mutations) > 0 {
			result = append(result, transition)
		}
	}
	sort.Slice(result, func(left, right int) bool {
		return locationLess(
			result[left].Mutations[0].Target,
			result[right].Mutations[0].Target,
		)
	})
	return result, nil
}

func (builder *preparationBuilder) transition(
	configTarget domain.Location,
	resources map[string]bool,
) (Transition, error) {
	var targets []domain.Location
	for target := range builder.touch {
		if target == configTarget || builder.groupByTarget[target] == configTarget {
			targets = append(targets, target)
		}
	}
	sort.Slice(targets, func(left, right int) bool {
		return locationLess(targets[left], targets[right])
	})
	resourceIDs := sortedStringSet(resources)
	mutations := make([]FileMutation, 0, len(targets))
	for _, target := range targets {
		mutation, err := builder.mutation(target)
		if err != nil {
			return Transition{}, err
		}
		if mutation != nil {
			mutations = append(mutations, *mutation)
		}
	}
	return Transition{ResourceIDs: resourceIDs, Mutations: mutations}, nil
}

func (builder *preparationBuilder) mutation(
	target domain.Location,
) (*FileMutation, error) {
	snapshot, exists := builder.files[target]
	if !exists {
		return nil, fmt.Errorf("target snapshot is unavailable")
	}
	after := builder.docs[target].Indented()
	if snapshot.present && bytes.Equal(snapshot.raw, after) {
		return nil, nil
	}
	mode, err := preparedMode(snapshot)
	if err != nil {
		return nil, err
	}
	return &FileMutation{
		Disposition: MutationPresent,
		Target:      target,
		Before:      beforeImage(snapshot),
		After: AfterImage{
			Exists:  true,
			Content: append([]byte(nil), after...),
			Mode:    mode,
		},
	}, nil
}

func beforeImage(snapshot fileSnapshot) BeforeImage {
	if !snapshot.present {
		return BeforeImage{}
	}
	digest := sha256.Sum256(snapshot.raw)
	return BeforeImage{
		Exists: true, SHA256: hex.EncodeToString(digest[:]),
		Mode: snapshot.mode, Device: snapshot.device, Inode: snapshot.inode,
		BirthSeconds:     snapshot.birthSeconds,
		BirthNanoseconds: snapshot.birthNanoseconds,
	}
}

func preparedMode(snapshot fileSnapshot) (uint32, error) {
	if !snapshot.present {
		return privateConfigurationMode, nil
	}
	if snapshot.device == 0 || snapshot.inode == 0 ||
		snapshot.birthSeconds <= 0 ||
		snapshot.birthNanoseconds < 0 ||
		snapshot.birthNanoseconds >= 1_000_000_000 ||
		snapshot.mode&0o400 == 0 {
		return 0, fmt.Errorf("existing target metadata is incomplete or unsafe")
	}
	return snapshot.mode & privateConfigurationMode, nil
}

func locationLess(left, right domain.Location) bool {
	if left.Root != right.Root {
		return left.Root < right.Root
	}
	return left.Path < right.Path
}

func sortedStringSet(values map[string]bool) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func rejectPhysicalAliases(transitions []Transition) error {
	type identity struct {
		device uint64
		inode  uint64
	}
	seen := make(map[identity]domain.Location)
	for _, transition := range transitions {
		for _, mutation := range transition.Mutations {
			if !mutation.Before.Exists {
				continue
			}
			key := identity{
				device: mutation.Before.Device,
				inode:  mutation.Before.Inode,
			}
			if previous, exists := seen[key]; exists &&
				previous != mutation.Target {
				return fmt.Errorf(
					"configuration targets %v and %v share one physical file",
					previous,
					mutation.Target,
				)
			}
			seen[key] = mutation.Target
		}
	}
	return nil
}
