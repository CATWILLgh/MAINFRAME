package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestDecodeCredentialInstanceChangeAcceptsCreate(t *testing.T) {
	request, err := decodeCredentialInstanceChange(strings.NewReader(`{
		"schema_version":1,
		"kind":"mainframe-credential-instance-change",
		"operation":"create",
		"instance":{
			"id":"context7-home",
			"service_id":"context7",
			"name":"Home",
			"purpose":"Personal research",
			"credentials":[{
				"role_id":"api-key",
				"secret":{"backend":"secret-env","name":"CONTEXT7_SHARED_KEY"}
			}]
		}
	}`))
	if err != nil {
		t.Fatalf("decode change: %v", err)
	}
	if request.Operation != credentialOperationCreate ||
		request.Instance.ID != "context7-home" ||
		request.Instance.Credentials[0].Secret.Name != "CONTEXT7_SHARED_KEY" {
		t.Fatalf("request = %#v", request)
	}
}

func TestDecodeCredentialInstanceChangeRejectsAmbiguousInput(t *testing.T) {
	tests := map[string]string{
		"null":          `null`,
		"unknown field": `{"schema_version":1,"kind":"mainframe-credential-instance-change","operation":"create","instance":{},"extra":true}`,
		"duplicate key": `{"schema_version":1,"schema_version":1,"kind":"mainframe-credential-instance-change","operation":"create","instance":{}}`,
		"case alias":    `{"schema_version":1,"kind":"mainframe-credential-instance-change","Kind":"mainframe-credential-instance-change","operation":"create","instance":{}}`,
		"trailing JSON": `{"schema_version":1,"kind":"mainframe-credential-instance-change","operation":"create","instance":{}} {}`,
		"wrong version": `{"schema_version":2,"kind":"mainframe-credential-instance-change","operation":"create","instance":{}}`,
		"wrong kind":    `{"schema_version":1,"kind":"other","operation":"create","instance":{}}`,
		"edit without id": `{
			"schema_version":1,
			"kind":"mainframe-credential-instance-change",
			"operation":"edit",
			"instance":{"id":"context7-home"}
		}`,
		"create with id": `{
			"schema_version":1,
			"kind":"mainframe-credential-instance-change",
			"operation":"create",
			"instance_id":"context7-home",
			"instance":{"id":"context7-home"}
		}`,
	}
	for name, input := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeCredentialInstanceChange(
				strings.NewReader(input),
			); err == nil {
				t.Fatal("decode succeeded")
			}
		})
	}
}

func TestCredentialInstanceErrorsDoNotEchoRejectedValues(t *testing.T) {
	const marker = "must-not-appear-in-output"
	input := `{
		"schema_version":1,
		"kind":"mainframe-credential-instance-change",
		"operation":"create",
		"instance":{
			"id":"context7-home",
			"service_id":"context7",
			"name":"Home",
			"purpose":"Personal research",
			"credentials":[{
				"role_id":"api-key",
				"secret":{
					"backend":"secret-env",
					"name":"CONTEXT7_HOME_KEY",
					"value":"` + marker + `"
				}
			}]
		}
	}`
	assertCredentialReviewRejectsWithoutEcho(t, input, marker)
	input = `{
		"schema_version":1,
		"kind":"` + marker + `",
		"operation":"create",
		"instance":{}
	}`
	assertCredentialReviewRejectsWithoutEcho(t, input, marker)
}

func assertCredentialReviewRejectsWithoutEcho(
	t *testing.T,
	input string,
	marker string,
) {
	t.Helper()
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "instance", "review"},
		strings.NewReader(input),
		&stdout,
		&stderr,
	)
	if exitCode != 2 ||
		strings.Contains(stdout.String()+stderr.String(), marker) {
		t.Fatalf(
			"rejected input was echoed: exit=%d stdout=%q stderr=%q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}

func TestDecodeCredentialApplyRequestRequiresVersionedSingleChangeScope(
	t *testing.T,
) {
	valid := `{
		"schema_version":1,
		"kind":"mainframe-credential-instances-apply",
		"operation":"create",
		"instance_id":"context7-home",
		"instances":[]
	}`
	request, err := decodeCredentialApplyRequest(strings.NewReader(valid))
	if err != nil {
		t.Fatalf("decode apply: %v", err)
	}
	if request.Operation != credentialOperationCreate ||
		request.InstanceID != "context7-home" ||
		request.Instances == nil {
		t.Fatalf("request = %#v", request)
	}
	tests := []string{
		`{"schema_version":2,"kind":"mainframe-credential-instances-apply","operation":"create","instance_id":"context7-home","instances":[]}`,
		`{"schema_version":1,"kind":"other","operation":"create","instance_id":"context7-home","instances":[]}`,
		`{"schema_version":1,"kind":"mainframe-credential-instances-apply","operation":"remove","instance_id":"context7-home","instances":[]}`,
		`{"schema_version":1,"kind":"mainframe-credential-instances-apply","operation":"create","instance_id":"","instances":[]}`,
		`{"schema_version":1,"kind":"mainframe-credential-instances-apply","operation":"create","instance_id":"context7-home","instances":null}`,
	}
	for _, input := range tests {
		if _, err := decodeCredentialApplyRequest(
			strings.NewReader(input),
		); err == nil {
			t.Fatalf("accepted invalid apply request %s", input)
		}
	}
}

func TestRequestedCredentialChangeMustMatchReviewedChangeExactly(t *testing.T) {
	before := credentialcatalog.Instance{
		ID: "context7-home", ServiceID: "context7",
		Name: "Home", Purpose: "Personal research",
		Credentials: []credentialcatalog.CredentialBinding{{
			RoleID: "api-key",
			Secret: credentialcatalog.SecretReference{
				Backend: "secret-env", Name: "CONTEXT7_SHARED_KEY",
			},
		}},
	}
	after := before.Clone()
	after.Name = "Home research"
	expected := credentialcatalog.InstanceChange{
		Kind: credentialcatalog.ChangeUpdate, Before: before, After: after,
	}
	if err := requireExactCredentialChange(
		[]credentialcatalog.InstanceChange{expected},
		expected,
	); err != nil {
		t.Fatalf("matching change rejected: %v", err)
	}

	unrelated := expected
	unrelated.After.Purpose = "Concurrent edit"
	if err := requireExactCredentialChange(
		[]credentialcatalog.InstanceChange{expected, unrelated},
		expected,
	); err == nil {
		t.Fatal("additional reviewed change accepted")
	}
	if err := requireExactCredentialChange(
		[]credentialcatalog.InstanceChange{unrelated},
		expected,
	); err == nil {
		t.Fatal("different reviewed change accepted")
	}
}

func TestEditCredentialInstancesUsesNormalizedDesiredChange(t *testing.T) {
	useCredentialsEnvironment(t)
	definitions, _, err := loadCredentialCatalog()
	if err != nil {
		t.Fatalf("load catalog: %v", err)
	}
	a := testProtocolInstance()
	a.ID, a.Name = "context7-a", "A"
	source := testProtocolInstance()
	source.ID, source.Name = "context7-source", "Source"
	z := testProtocolInstance()
	z.ID, z.Name = "context7-z", "Z"
	current, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{source, z, a},
		definitions,
	)
	if err != nil {
		t.Fatalf("build current: %v", err)
	}
	replacement := source.Clone()
	replacement.Credentials[0].Requirements = []credentialcatalog.Requirement{
		{
			Action: "use", InstanceID: "context7-z", RoleID: "api-key",
			Summary: "Use Z first in the input",
		},
		{
			Action: "use", InstanceID: "context7-a", RoleID: "api-key",
			Summary: "Use A second in the input",
		},
	}
	request := credentialInstanceChangeRequest{
		Operation:  credentialOperationEdit,
		InstanceID: string(replacement.ID),
	}
	desired, expected, err := editCredentialInstances(
		credentialMachineSession{
			definitions: definitions,
			current:     current,
		},
		request,
		replacement,
	)
	if err != nil {
		t.Fatalf("edit instances: %v", err)
	}
	requirements := expected.After.Credentials[0].Requirements
	if len(requirements) != 2 ||
		requirements[0].InstanceID != "context7-a" ||
		requirements[1].InstanceID != "context7-z" {
		t.Fatalf("normalized requirements = %#v", requirements)
	}
	reviewed, err := credentialcatalog.PlanInstanceChanges(current, desired)
	if err != nil {
		t.Fatalf("plan normalized change: %v", err)
	}
	if err := requireExactCredentialChange(reviewed, expected); err != nil {
		t.Fatalf("normalized change mismatch: %v", err)
	}
}

func TestCredentialOnlySnapshotBuilderRejectsOtherSubsystemsBeforeObservation(
	t *testing.T,
) {
	observations := 0
	builder := credentialOnlySnapshotBuilder{
		expected: executor.ReleaseIdentity{ID: "release", IndexSHA256: "digest"},
		observe: func() (credentialObservation, error) {
			observations++
			return credentialObservation{}, nil
		},
	}
	requests := []application.Request{
		{Components: []domain.ComponentID{domain.ComponentCodex}},
		{Diagnostics: diagnostics.Desired{Configured: true}},
		{},
	}
	for _, request := range requests {
		if _, err := builder.Build(request); err == nil {
			t.Fatalf("Build(%#v) succeeded", request)
		}
	}
	if observations != 0 {
		t.Fatalf("observations = %d, want 0", observations)
	}
}

func TestCredentialOnlySnapshotBuilderPinsReleaseAndUsesFirstObservation(
	t *testing.T,
) {
	identity := executor.ReleaseIdentity{ID: "release", IndexSHA256: "digest"}
	first := credentialObservation{release: identity}
	observations := 0
	builder := credentialOnlySnapshotBuilder{
		expected: identity,
		first:    &first,
		observe: func() (credentialObservation, error) {
			observations++
			return credentialObservation{
				release: executor.ReleaseIdentity{
					ID: "changed", IndexSHA256: "different",
				},
			}, nil
		},
	}
	desired := credentialcatalog.Instances{}
	request := application.Request{CredentialInstances: &desired}
	snapshot, err := builder.Build(request)
	if err != nil {
		t.Fatalf("first Build() error = %v", err)
	}
	if snapshot.Release != identity || observations != 0 {
		t.Fatalf(
			"first snapshot = %#v, observations = %d",
			snapshot.Release,
			observations,
		)
	}
	if _, err := builder.Build(request); err == nil ||
		!strings.Contains(err.Error(), "release identity changed") {
		t.Fatalf("second Build() error = %v", err)
	}
	if observations != 1 {
		t.Fatalf("observations = %d, want 1", observations)
	}
}
