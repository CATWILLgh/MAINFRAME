package configuration_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestExactJSONDocumentExplicitRemoval(t *testing.T) {
	resource := exactConfigurationResource()
	before := []byte(resource.ExactJSONExemplar)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			resource.Target: preparedEntry(before, 0o600, 69),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID:  resource.ID,
		Disposition: configuration.ExactJSONAbsent,
	}}
	plan, err := inspection.PlanExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	want := configuration.Change{
		ResourceID: resource.ID, ComponentID: domain.ComponentCodex,
		Kind: configuration.ChangeRemove,
	}
	if !reflect.DeepEqual(plan.Changes, []configuration.Change{want}) {
		t.Fatalf("changes = %#v", plan.Changes)
	}
	prepared, err := inspection.PrepareExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	mutation := prepared.Transitions()[0].Mutations[0]
	if !mutation.Before.Exists || mutation.After.Exists ||
		len(mutation.After.Content) != 0 || mutation.After.Mode != 0 {
		t.Fatalf("mutation = %#v", mutation)
	}
}

func TestExactJSONDocumentOmissionLeavesExistingResourceUntouched(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			resource.Target: preparedEntry(
				[]byte(resource.ExactJSONExemplar),
				0o600,
				70,
			),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	plan, err := inspection.PlanExactJSONDocuments(nil)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	prepared, err := inspection.PrepareExactJSONDocuments(nil)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	if len(plan.Changes) != 0 || len(prepared.Transitions()) != 0 {
		t.Fatalf("omission changed resource: %#v, %#v", plan, prepared.Transitions())
	}
}

func TestExactJSONDocumentAlreadyAbsentRemovalIsNoOp(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID:  resource.ID,
		Disposition: configuration.ExactJSONAbsent,
	}}
	plan, err := inspection.PlanExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	prepared, err := inspection.PrepareExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	if len(plan.Changes) != 0 || len(prepared.Transitions()) != 0 {
		t.Fatalf("absent removal was not a no-op: %#v, %#v", plan, prepared.Transitions())
	}
}

func TestExactJSONDocumentDispositionValidatesDocumentPresence(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	tests := []configuration.ExactJSONDocument{
		{
			ResourceID:  resource.ID,
			Disposition: configuration.ExactJSONAbsent,
			Document:    []byte(resource.ExactJSONExemplar),
		},
		{
			ResourceID:  resource.ID,
			Disposition: configuration.ExactJSONPresent,
		},
	}
	for _, desired := range tests {
		if _, err := inspection.PlanExactJSONDocuments(
			[]configuration.ExactJSONDocument{desired},
		); err == nil {
			t.Fatalf("invalid desired state accepted: %#v", desired)
		}
	}
}

func TestExactJSONDocumentInvalidCurrentSchemaBlocksRemoval(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			resource.Target: preparedEntry(
				[]byte(`{"schema_version":1,"events":true}`),
				0o600,
				102,
			),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID:  resource.ID,
		Disposition: configuration.ExactJSONAbsent,
	}}
	plan, err := inspection.PlanExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	if len(plan.Issues) != 1 ||
		plan.Issues[0].Reason != configuration.JSONDocumentInvalid {
		t.Fatalf("issues = %#v", plan.Issues)
	}
	if _, err := inspection.PrepareExactJSONDocuments(desired); err == nil {
		t.Fatal("invalid current exact JSON document was removed")
	}
}
