package configuration_test

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestExactJSONDocumentRequiresExplicitRuntimeDesiredState(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	generic, err := inspection.Plan([]domain.ComponentID{domain.ComponentCodex})
	if err != nil {
		t.Fatalf("Plan() error = %v", err)
	}
	if !reflect.DeepEqual(generic, configuration.Plan{}) {
		t.Fatalf("generic plan implicitly used exemplar: %#v", generic)
	}
	exact, err := inspection.PlanExactJSONDocuments(nil)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	if !reflect.DeepEqual(exact, configuration.Plan{}) {
		t.Fatalf("empty runtime desired state planned changes: %#v", exact)
	}
}

func TestExactJSONDocumentPlansAndPreparesCanonicalPrivateReplacement(t *testing.T) {
	resource := exactConfigurationResource()
	target := resource.Target
	before := []byte(`{"schema_version":1,"events":false,"feedback":false}`)
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			target: preparedEntry(before, 0o400, 71),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID: resource.ID,
		Document:   []byte(`{"feedback":true,"events":true,"schema_version":1}`),
	}}
	plan, err := inspection.PlanExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PlanExactJSONDocuments() error = %v", err)
	}
	wantChange := configuration.Change{
		ResourceID: resource.ID, ComponentID: domain.ComponentCodex,
		Kind: configuration.ChangeUpdate,
	}
	if !reflect.DeepEqual(plan.Changes, []configuration.Change{wantChange}) {
		t.Fatalf("changes = %#v", plan.Changes)
	}
	prepared, err := inspection.PrepareExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 1 {
		t.Fatalf("transitions = %#v", transitions)
	}
	mutation := transitions[0].Mutations[0]
	if mutation.Target != target || mutation.Mode != 0o600 ||
		string(mutation.After) !=
			"{\n  \"events\": true,\n  \"feedback\": true,\n  \"schema_version\": 1\n}\n" {
		t.Fatalf("mutation = %#v", mutation)
	}
}

func TestExactJSONDocumentUsesSemanticEqualityButRepairsMode(t *testing.T) {
	resource := exactConfigurationResource()
	target := resource.Target
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			target: preparedEntry(
				[]byte("{\n \"feedback\": false,\n \"events\": true,\n \"schema_version\": 1\n}\n"),
				0o644,
				81,
			),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID: resource.ID,
		Document: []byte(
			`{"schema_version":1,"events":true,"feedback":false}`,
		),
	}}
	prepared, err := inspection.PrepareExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	mutation := prepared.Transitions()[0].Mutations[0]
	if mutation.Mode != 0o600 {
		t.Fatalf("mode = %04o, want 0600", mutation.Mode)
	}
}

func TestExactJSONDocumentSemanticEqualityAtPrivateModeIsNoOp(t *testing.T) {
	resource := exactConfigurationResource()
	target := resource.Target
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			target: preparedEntry(
				[]byte("{\n \"feedback\": false,\n \"events\": true,\n \"schema_version\": 1\n}\n"),
				0o600,
				91,
			),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID: resource.ID,
		Document: []byte(
			`{"schema_version":1,"events":true,"feedback":false}`,
		),
	}}
	prepared, err := inspection.PrepareExactJSONDocuments(desired)
	if err != nil {
		t.Fatalf("PrepareExactJSONDocuments() error = %v", err)
	}
	if len(prepared.Transitions()) != 0 {
		t.Fatalf("semantic no-op prepared transitions: %#v", prepared.Transitions())
	}
}

func TestExactJSONDocumentRejectsInvalidOrUnknownRuntimeDesiredState(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(nil),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	for _, desired := range []configuration.ExactJSONDocument{
		{ResourceID: resource.ID},
		{ResourceID: resource.ID, Document: []byte(`{"events":true}`)},
		{ResourceID: "unknown", Document: []byte(
			`{"schema_version":1,"events":true,"feedback":false}`,
		)},
	} {
		if _, err := inspection.PrepareExactJSONDocuments(
			[]configuration.ExactJSONDocument{desired},
		); err == nil {
			t.Fatalf("invalid desired state accepted: %#v", desired)
		}
	}
	valid := configuration.ExactJSONDocument{
		ResourceID: resource.ID,
		Document: []byte(
			`{"schema_version":1,"events":true,"feedback":false}`,
		),
	}
	if _, err := inspection.PrepareExactJSONDocuments(
		[]configuration.ExactJSONDocument{valid, valid},
	); err == nil {
		t.Fatal("duplicate exact JSON desired resource was accepted")
	}
}

func TestExactJSONDocumentInvalidCurrentSchemaBlocksPreparation(t *testing.T) {
	resource := exactConfigurationResource()
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{resource},
		preparedHost(map[domain.Location]hostfs.Entry{
			resource.Target: preparedEntry(
				[]byte(`{"schema_version":1,"events":true}`),
				0o600,
				101,
			),
		}),
	)
	if err != nil {
		t.Fatalf("Inspect() error = %v", err)
	}
	desired := []configuration.ExactJSONDocument{{
		ResourceID: resource.ID,
		Document: []byte(
			`{"schema_version":1,"events":true,"feedback":false}`,
		),
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
		t.Fatal("invalid current exact JSON document was overwritten")
	}
}

func exactConfigurationResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID: "codex.diagnostics", ComponentID: domain.ComponentCodex,
		Strategy:   releasecontract.StrategyExactJSONDocument,
		SourcePath: "bundles/codex/diagnostics.json",
		Target: domain.Location{
			Root: domain.RootCodexConfig, Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
}
