//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const context7HomeCreateRequest = `{
	"schema_version":1,
	"kind":"mainframe-credential-instance-change",
	"operation":"create",
	"instance":{
		"id":"context7-home","service_id":"context7",
		"name":"Home","purpose":"Personal research",
		"credentials":[{"role_id":"api-key","secret":{
			"backend":"secret-env","name":"CONTEXT7_SHARED_KEY"
		}}]
	}
}`

const context7WorkCreateRequest = `{
	"schema_version":1,
	"kind":"mainframe-credential-instance-change",
	"operation":"create",
	"instance":{
		"id":"context7-work","service_id":"context7",
		"name":"Work","purpose":"Company research",
		"credentials":[{"role_id":"api-key","secret":{
			"backend":"secret-env","name":"CONTEXT7_SHARED_KEY"
		}}]
	}
}`

const context7WorkEditRequest = `{
	"schema_version":1,
	"kind":"mainframe-credential-instance-change",
	"operation":"edit",
	"instance_id":"context7-work",
	"instance":{
		"id":"context7-work","service_id":"context7",
		"name":"Work research","purpose":"Company research",
		"credentials":[{"role_id":"api-key","secret":{
			"backend":"secret-env","name":"CONTEXT7_SHARED_KEY"
		}}]
	}
}`

type credentialReviewContract struct {
	SchemaVersion  int                        `json:"schema_version"`
	Kind           string                     `json:"kind"`
	Operation      string                     `json:"operation"`
	Changes        []credentialChangeContract `json:"changes"`
	ApplyRequest   credentialApplyContract    `json:"apply_request"`
	ExpectedReview string                     `json:"expected_review"`
}

type credentialChangeContract struct {
	Operation string                             `json:"operation"`
	Before    *machineCredentialInstanceContract `json:"before,omitempty"`
	After     *machineCredentialInstanceContract `json:"after,omitempty"`
}

type credentialApplyContract struct {
	SchemaVersion int                                 `json:"schema_version"`
	Kind          string                              `json:"kind"`
	Operation     string                              `json:"operation"`
	InstanceID    string                              `json:"instance_id"`
	Instances     []machineCredentialInstanceContract `json:"instances"`
}

type machineCredentialInstanceContract struct {
	ID          string                             `json:"id"`
	ServiceID   string                             `json:"service_id"`
	Name        string                             `json:"name"`
	Purpose     string                             `json:"purpose"`
	Locator     string                             `json:"locator,omitempty"`
	Credentials []machineCredentialBindingContract `json:"credentials"`
}

type machineCredentialBindingContract struct {
	RoleID       string                                 `json:"role_id"`
	Secret       credentialsSecretReference             `json:"secret"`
	Requirements []machineCredentialRequirementContract `json:"requirements,omitempty"`
}

type machineCredentialRequirementContract struct {
	Action     string `json:"action"`
	InstanceID string `json:"instance_id"`
	RoleID     string `json:"role_id"`
	Summary    string `json:"summary"`
}

type credentialCommandFixture struct {
	path string
}

type credentialApplyResultContract struct {
	SchemaVersion int      `json:"schema_version"`
	Kind          string   `json:"kind"`
	Applied       bool     `json:"applied"`
	Warnings      []string `json:"warnings"`
}

func TestCredentialInstanceReviewIsReadOnlyAndApplyWritesReviewedState(
	t *testing.T,
) {
	fixture := newCredentialCommandFixture(t)
	review := reviewCredentialChange(t, context7HomeCreateRequest)
	if _, err := os.Stat(fixture.path); !os.IsNotExist(err) {
		t.Fatalf("review created credential state: %v", err)
	}
	if review.SchemaVersion != 1 ||
		review.Kind != "mainframe-credential-instance-review" ||
		review.Operation != "create" ||
		len(review.Changes) != 1 ||
		review.Changes[0].Operation != "create" ||
		review.Changes[0].Before != nil ||
		review.Changes[0].After.ID != "context7-home" ||
		review.ExpectedReview == "" {
		t.Fatalf("review = %#v", review)
	}
	exitCode, applyOutput, applyErrors := applyCredentialReview(t, review)
	if exitCode != 0 {
		t.Fatalf(
			"apply exit = %d, stderr = %q",
			exitCode,
			applyErrors,
		)
	}
	info, err := os.Stat(fixture.path)
	if err != nil {
		t.Fatalf("stat applied credential state: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("credential state mode = %#o", info.Mode().Perm())
	}
	if strings.Contains(applyOutput, "CONTEXT7_SHARED_KEY") {
		t.Fatalf("apply output exposed a secret reference: %q", applyOutput)
	}
	var applied credentialApplyResultContract
	if err := json.Unmarshal([]byte(applyOutput), &applied); err != nil {
		t.Fatalf("decode apply response: %v", err)
	}
	if applied.SchemaVersion != 1 ||
		applied.Kind != "mainframe-credential-instance-apply-result" ||
		!applied.Applied ||
		applied.Warnings == nil {
		t.Fatalf("apply response = %#v", applied)
	}
	exitCode, _, applyErrors = applyCredentialReview(t, review)
	if exitCode == 0 ||
		!strings.Contains(applyErrors, "no longer applicable") {
		t.Fatalf(
			"repeated apply exit = %d, stderr = %q",
			exitCode,
			applyErrors,
		)
	}
}

func TestCredentialInstanceApplyRejectsChangedBeforeImage(t *testing.T) {
	fixture := newCredentialCommandFixture(t)
	review := reviewCredentialChange(t, context7HomeCreateRequest)
	empty := []byte(`{
  "schema_version": 1,
  "kind": "mainframe-credential-instances",
  "instances": []
}
`)
	if err := os.MkdirAll(filepath.Dir(fixture.path), 0o700); err != nil {
		t.Fatalf("create credential directory: %v", err)
	}
	if err := os.WriteFile(fixture.path, empty, 0o600); err != nil {
		t.Fatalf("write concurrent state: %v", err)
	}
	exitCode, _, applyErrors := applyCredentialReview(t, review)
	if exitCode == 0 || !strings.Contains(applyErrors, "review again") {
		t.Fatalf("apply exit = %d, stderr = %q", exitCode, applyErrors)
	}
	after, err := os.ReadFile(fixture.path)
	if err != nil {
		t.Fatalf("read concurrent state: %v", err)
	}
	if !bytes.Equal(after, empty) {
		t.Fatal("stale apply changed the credential state")
	}
}

func TestCredentialInstanceCommandsReuseReferenceAndEditOneInstance(
	t *testing.T,
) {
	newCredentialCommandFixture(t)
	executeCredentialChange(t, context7HomeCreateRequest)
	executeCredentialChange(t, context7WorkCreateRequest)
	review := executeCredentialChange(t, context7WorkEditRequest)
	if review.Changes[0].Operation != "edit" ||
		review.Changes[0].Before == nil ||
		review.Changes[0].Before.Name != "Work" ||
		review.Changes[0].After.Name != "Work research" {
		t.Fatalf("edit review = %#v", review)
	}
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "uses", "CONTEXT7_SHARED_KEY"},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)
	if exitCode != 0 {
		t.Fatalf("uses exit = %d, stderr = %q", exitCode, stderr.String())
	}
	var uses credentialUsesContract
	if err := json.Unmarshal(stdout.Bytes(), &uses); err != nil {
		t.Fatalf("decode uses: %v", err)
	}
	if len(uses.Uses) != 2 {
		t.Fatalf("uses = %#v", uses.Uses)
	}
}

func TestCredentialInstanceApplyRejectsPhysicalTargetDrift(t *testing.T) {
	fixture := newCredentialCommandFixture(t)
	review := reviewCredentialChange(t, context7HomeCreateRequest)
	otherConfig := canonicalTempDir(t)
	t.Setenv("XDG_CONFIG_HOME", otherConfig)
	exitCode, _, stderr := applyCredentialReview(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "review again") {
		t.Fatalf("apply exit = %d, stderr = %q", exitCode, stderr)
	}
	otherPath := filepath.Join(
		otherConfig,
		"credentials",
		"mainframe",
		"instances.json",
	)
	for _, path := range []string{fixture.path, otherPath} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("target drift wrote %q: %v", path, err)
		}
	}
}

func executeCredentialChange(
	t *testing.T,
	change string,
) credentialReviewContract {
	t.Helper()
	review := reviewCredentialChange(t, change)
	exitCode, _, stderr := applyCredentialReview(t, review)
	if exitCode != 0 {
		t.Fatalf("apply exit = %d, stderr = %q", exitCode, stderr)
	}
	return review
}

func newCredentialCommandFixture(t *testing.T) credentialCommandFixture {
	t.Helper()
	usePlanRelease(t)
	t.Setenv("HOME", canonicalTempDir(t))
	config := canonicalTempDir(t)
	t.Setenv("XDG_CONFIG_HOME", config)
	t.Setenv("XDG_STATE_HOME", canonicalTempDir(t))
	return credentialCommandFixture{path: filepath.Join(
		config,
		"credentials",
		"mainframe",
		"instances.json",
	)}
}

func reviewCredentialChange(
	t *testing.T,
	change string,
) credentialReviewContract {
	t.Helper()
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "instance", "review"},
		strings.NewReader(change),
		&stdout,
		&stderr,
	)
	if exitCode != 0 {
		t.Fatalf("review exit = %d, stderr = %q", exitCode, stderr.String())
	}
	var review credentialReviewContract
	if err := json.Unmarshal(stdout.Bytes(), &review); err != nil {
		t.Fatalf("decode review: %v", err)
	}
	return review
}

func applyCredentialReview(
	t *testing.T,
	review credentialReviewContract,
) (int, string, string) {
	t.Helper()
	payload, err := json.Marshal(review.ApplyRequest)
	if err != nil {
		t.Fatalf("encode apply request: %v", err)
	}
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{
			"credentials", "instance", "apply",
			"--confirm", review.ExpectedReview,
		},
		bytes.NewReader(payload),
		&stdout,
		&stderr,
	)
	return exitCode, stdout.String(), stderr.String()
}
