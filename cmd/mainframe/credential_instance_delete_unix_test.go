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

const context7HomeDeleteRequest = `{
	"schema_version":1,
	"kind":"mainframe-credential-instance-change",
	"operation":"delete",
	"instance_id":"context7-home"
}`

const context7WorkDeleteRequest = `{
	"schema_version":1,
	"kind":"mainframe-credential-instance-change",
	"operation":"delete",
	"instance_id":"context7-work"
}`

func TestCredentialInstanceDeletePublishesCatalogWithoutDeletingSecretValue(
	t *testing.T,
) {
	fixture := newCredentialCommandFixture(t)
	executeCredentialChange(t, context7HomeCreateRequest)
	executeCredentialChange(t, context7WorkCreateRequest)
	secretStore := filepath.Join(canonicalTempDir(t), "secrets.env")
	secretPayload := []byte("CONTEXT7_SHARED_KEY=must-remain\n")
	if err := os.WriteFile(secretStore, secretPayload, 0o600); err != nil {
		t.Fatalf("write secret store: %v", err)
	}

	review := reviewCredentialChange(t, context7HomeDeleteRequest)
	if review.Operation != "delete" ||
		len(review.Changes) != 1 ||
		review.Changes[0].Operation != "delete" ||
		review.Changes[0].Before == nil ||
		review.Changes[0].Before.ID != "context7-home" ||
		review.Changes[0].After != nil ||
		len(review.ApplyRequest.Instances) != 1 ||
		review.ApplyRequest.Instances[0].ID != "context7-work" {
		t.Fatalf("delete review = %#v", review)
	}
	exitCode, _, stderr := applyCredentialReview(t, review)
	if exitCode != 0 {
		t.Fatalf("delete apply exit = %d, stderr = %q", exitCode, stderr)
	}
	payload, err := os.ReadFile(fixture.path)
	if err != nil {
		t.Fatalf("read credential catalog: %v", err)
	}
	if strings.Contains(string(payload), "context7-home") {
		t.Fatalf("deleted instance remains in catalog: %s", payload)
	}
	var usesOutput, usesErrors bytes.Buffer
	exitCode = run(
		[]string{"credentials", "uses", "CONTEXT7_SHARED_KEY"},
		strings.NewReader(""),
		&usesOutput,
		&usesErrors,
	)
	if exitCode != 0 {
		t.Fatalf("uses exit = %d, stderr = %q", exitCode, usesErrors.String())
	}
	var uses credentialUsesContract
	if err := json.Unmarshal(usesOutput.Bytes(), &uses); err != nil {
		t.Fatalf("decode uses: %v", err)
	}
	if len(uses.Uses) != 1 || uses.Uses[0].InstanceID != "context7-work" {
		t.Fatalf("uses after delete = %#v", uses.Uses)
	}
	afterSecret, err := os.ReadFile(secretStore)
	if err != nil {
		t.Fatalf("read secret store: %v", err)
	}
	if !bytes.Equal(afterSecret, secretPayload) {
		t.Fatalf("delete changed secret store: %q", afterSecret)
	}
	exitCode, _, stderr = applyCredentialReview(t, review)
	if exitCode == 0 ||
		!strings.Contains(stderr, "no longer applicable") {
		t.Fatalf("repeated delete exit = %d, stderr = %q", exitCode, stderr)
	}
	executeCredentialChange(t, context7WorkDeleteRequest)
	payload, err = os.ReadFile(fixture.path)
	if err != nil {
		t.Fatalf("read empty credential catalog: %v", err)
	}
	if strings.Contains(string(payload), `"id"`) {
		t.Fatalf("last delete did not publish an empty catalog: %s", payload)
	}
}

func TestCredentialInstanceDeleteRejectsStaleAndDependencyTarget(t *testing.T) {
	fixture := newCredentialCommandFixture(t)
	executeCredentialChange(t, context7HomeCreateRequest)
	review := reviewCredentialChange(t, context7HomeDeleteRequest)
	executeCredentialChange(t, context7WorkCreateRequest)
	beforeStaleApply, err := os.ReadFile(fixture.path)
	if err != nil {
		t.Fatalf("read catalog before stale apply: %v", err)
	}
	exitCode, _, stderr := applyCredentialReview(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "review again") {
		t.Fatalf("stale delete exit = %d, stderr = %q", exitCode, stderr)
	}
	afterStaleApply, err := os.ReadFile(fixture.path)
	if err != nil {
		t.Fatalf("read catalog after stale apply: %v", err)
	}
	if !bytes.Equal(afterStaleApply, beforeStaleApply) {
		t.Fatal("stale delete changed the credential catalog")
	}

	dependentEdit := strings.Replace(
		context7WorkEditRequest,
		`"credentials":[{"role_id":"api-key","secret":{`,
		`"credentials":[{"role_id":"api-key","requirements":[{
			"action":"use","instance_id":"context7-home","role_id":"api-key",
			"summary":"Use home credentials"
		}],"secret":{`,
		1,
	)
	executeCredentialChange(t, dependentEdit)
	var stdout, errors bytes.Buffer
	exitCode = run(
		[]string{"credentials", "instance", "review"},
		strings.NewReader(context7HomeDeleteRequest),
		&stdout,
		&errors,
	)
	if exitCode == 0 ||
		!strings.Contains(errors.String(), "requirement target") {
		t.Fatalf(
			"dependency delete exit = %d, stderr = %q",
			exitCode,
			errors.String(),
		)
	}
}

func TestCredentialInstanceDeleteRejectsManagedAdapterReference(t *testing.T) {
	fixture := newSecretRetirementFixture(t)
	executeCredentialChange(t, context7HomeCreateRequest)
	writeOpenCodeSecretRegistry(t, fixture.config, "CONTEXT7_SHARED_KEY")

	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "instance", "review"},
		strings.NewReader(context7HomeDeleteRequest),
		&stdout,
		&stderr,
	)
	if exitCode == 0 ||
		!strings.Contains(stderr.String(), "managed adapter registry") {
		t.Fatalf(
			"managed delete review exit/output = %d/%q/%q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}

func TestCredentialInstanceDeleteRechecksManagedAdaptersDuringApply(
	t *testing.T,
) {
	fixture := newSecretRetirementFixture(t)
	executeCredentialChange(t, context7HomeCreateRequest)
	review := reviewCredentialChange(t, context7HomeDeleteRequest)
	before, err := os.ReadFile(filepath.Join(
		fixture.config,
		"credentials",
		"mainframe",
		"instances.json",
	))
	if err != nil {
		t.Fatal(err)
	}
	writeOpenCodeSecretRegistry(t, fixture.config, "CONTEXT7_SHARED_KEY")

	exitCode, _, stderr := applyCredentialReview(t, review)
	if exitCode == 0 ||
		!strings.Contains(stderr, "managed adapter registry") {
		t.Fatalf("managed delete apply exit/stderr = %d/%q", exitCode, stderr)
	}
	after, err := os.ReadFile(filepath.Join(
		fixture.config,
		"credentials",
		"mainframe",
		"instances.json",
	))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(before, after) {
		t.Fatal("blocked managed delete changed the credential catalog")
	}
}

func TestMalformedManagedRegistryDoesNotBlockCredentialCreate(t *testing.T) {
	fixture := newSecretRetirementFixture(t)
	target := filepath.Join(
		fixture.config,
		"opencode",
		"opencode.json.mainframe-mcp.json",
	)
	if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(target, []byte(`{"version":1,"servers":`), 0o600); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "instance", "review"},
		strings.NewReader(context7HomeCreateRequest),
		&stdout,
		&stderr,
	)
	if exitCode != 0 {
		t.Fatalf(
			"credential create review exit/output = %d/%q/%q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}
