//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

type secretRetirementReviewContract struct {
	SchemaVersion  int                           `json:"schema_version"`
	Kind           string                        `json:"kind"`
	ApplyRequest   secretRetirementApplyContract `json:"apply_request"`
	ExpectedReview string                        `json:"expected_review"`
}

type secretRetirementApplyContract struct {
	SchemaVersion      int                       `json:"schema_version"`
	Kind               string                    `json:"kind"`
	Secret             credentialSecretReference `json:"secret"`
	ExpectedGeneration string                    `json:"expected_generation"`
}

func TestSecretRetirementPrepareAndApplyDeleteOnlyReviewedGeneration(
	t *testing.T,
) {
	newSecretRetirementFixture(t)
	createStoredSecret(t, "RETIRED_KEY", "value-not-for-output")

	review := prepareSecretRetirement(t, "RETIRED_KEY")
	rawReview, err := json.Marshal(review)
	if err != nil {
		t.Fatal(err)
	}
	if review.SchemaVersion != 1 ||
		review.Kind != "mainframe-credential-secret-retirement-review" ||
		review.ApplyRequest.Secret.Name != "RETIRED_KEY" ||
		review.ApplyRequest.ExpectedGeneration == "" ||
		!credentialConfirmationPattern.MatchString(review.ExpectedReview) ||
		bytes.Contains(rawReview, []byte("value-not-for-output")) {
		t.Fatalf("unsafe review = %s", rawReview)
	}

	exitCode, stdout, stderr := applySecretRetirement(t, review)
	if exitCode != 0 || strings.Contains(stdout+stderr, "value-not-for-output") {
		t.Fatalf("apply exit/output = %d/%q/%q", exitCode, stdout, stderr)
	}
	var result struct {
		SchemaVersion int      `json:"schema_version"`
		Kind          string   `json:"kind"`
		Applied       bool     `json:"applied"`
		Warnings      []string `json:"warnings"`
	}
	if err := json.Unmarshal([]byte(stdout), &result); err != nil {
		t.Fatalf("decode result: %v", err)
	}
	if result.SchemaVersion != 1 ||
		result.Kind != "mainframe-credential-secret-retirement-apply-result" ||
		!result.Applied ||
		len(result.Warnings) != 2 {
		t.Fatalf("result = %#v", result)
	}
	exitCode, _, stderr = applySecretRetirement(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "store changed") {
		t.Fatalf("repeat exit/stderr = %d/%q", exitCode, stderr)
	}
}

func TestSecretRetirementApplyRejectsStaleDigestAndStoreGeneration(
	t *testing.T,
) {
	t.Run("digest", func(t *testing.T) {
		newSecretRetirementFixture(t)
		createStoredSecret(t, "RETIRED_KEY", "first")
		review := prepareSecretRetirement(t, "RETIRED_KEY")
		review.ExpectedReview = "sha256:" + strings.Repeat("0", 64)
		exitCode, _, stderr := applySecretRetirement(t, review)
		if exitCode == 0 || !strings.Contains(stderr, "review confirmation is stale") {
			t.Fatalf("apply exit/stderr = %d/%q", exitCode, stderr)
		}
	})
	t.Run("generation", func(t *testing.T) {
		newSecretRetirementFixture(t)
		createStoredSecret(t, "RETIRED_KEY", "first")
		review := prepareSecretRetirement(t, "RETIRED_KEY")
		setStoredSecret(t, "RETIRED_KEY", "second")
		exitCode, _, stderr := applySecretRetirement(t, review)
		if exitCode == 0 || !strings.Contains(stderr, "store changed") {
			t.Fatalf("apply exit/stderr = %d/%q", exitCode, stderr)
		}
	})
}

func TestSecretRetirementApplyUsesSharedMainframeTransactionLock(t *testing.T) {
	fixture := newSecretRetirementFixture(t)
	createStoredSecret(t, "RETIRED_KEY", "value")
	review := prepareSecretRetirement(t, "RETIRED_KEY")
	state, err := executor.OpenUnixState(filepath.Join(fixture.state, "mainframe"))
	if err != nil {
		t.Fatal(err)
	}
	defer state.Close()
	lock, err := state.Lock()
	if err != nil {
		t.Fatal(err)
	}
	defer lock.Unlock()

	exitCode, _, stderr := applySecretRetirement(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "acquire transaction lock") {
		t.Fatalf("apply exit/stderr = %d/%q", exitCode, stderr)
	}
}

func TestSecretRetirementRejectsCatalogAndManagedRegistryReferences(
	t *testing.T,
) {
	t.Run("catalog", func(t *testing.T) {
		newSecretRetirementFixture(t)
		createStoredSecret(t, "CONTEXT7_SHARED_KEY", "value")
		executeCredentialChange(t, context7HomeCreateRequest)
		exitCode, _, stderr := runSecretRetirementPrepare(
			t,
			"CONTEXT7_SHARED_KEY",
		)
		if exitCode == 0 || !strings.Contains(stderr, "credential catalog") {
			t.Fatalf("prepare exit/stderr = %d/%q", exitCode, stderr)
		}
	})
	t.Run("managed registry recheck", func(t *testing.T) {
		fixture := newSecretRetirementFixture(t)
		createStoredSecret(t, "RETIRED_KEY", "value")
		review := prepareSecretRetirement(t, "RETIRED_KEY")
		writeOpenCodeSecretRegistry(t, fixture.config, "RETIRED_KEY")
		exitCode, _, stderr := applySecretRetirement(t, review)
		if exitCode == 0 || !strings.Contains(stderr, "managed adapter registry") {
			t.Fatalf("apply exit/stderr = %d/%q", exitCode, stderr)
		}
	})
}

func TestSecretRetirementFailsClosedOnMalformedManagedRegistry(t *testing.T) {
	fixture := newSecretRetirementFixture(t)
	createStoredSecret(t, "RETIRED_KEY", "value")
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
	exitCode, stdout, stderr := runSecretRetirementPrepare(t, "RETIRED_KEY")
	if exitCode == 0 ||
		stdout != "" ||
		!strings.Contains(stderr, "ownership registry is invalid") {
		t.Fatalf("prepare exit/output = %d/%q/%q", exitCode, stdout, stderr)
	}
}

type secretRetirementFixture struct {
	config string
	state  string
}

func newSecretRetirementFixture(t *testing.T) secretRetirementFixture {
	t.Helper()
	usePlanRelease(t)
	t.Setenv("HOME", canonicalTempDir(t))
	config := canonicalTempDir(t)
	t.Setenv("XDG_CONFIG_HOME", config)
	state := canonicalTempDir(t)
	t.Setenv("XDG_STATE_HOME", state)
	return secretRetirementFixture{config: config, state: state}
}

func createStoredSecret(t *testing.T, name, value string) {
	t.Helper()
	runHiddenSecretMutation(t, []string{"create-stdin", name}, value)
}

func setStoredSecret(t *testing.T, name, value string) {
	t.Helper()
	runHiddenSecretMutation(t, []string{"set", name, value}, "")
}

func runHiddenSecretMutation(t *testing.T, args []string, input string) {
	t.Helper()
	var stdout, stderr bytes.Buffer
	command := append([]string{"_secret-store"}, args...)
	if code := run(
		command,
		strings.NewReader(input),
		&stdout,
		&stderr,
	); code != 0 {
		t.Fatalf("secret mutation exit = %d, stderr = %q", code, stderr.String())
	}
}

func prepareSecretRetirement(
	t *testing.T,
	name string,
) secretRetirementReviewContract {
	t.Helper()
	exitCode, stdout, stderr := runSecretRetirementPrepare(t, name)
	if exitCode != 0 {
		t.Fatalf("prepare exit = %d, stderr = %q", exitCode, stderr)
	}
	var review secretRetirementReviewContract
	if err := json.Unmarshal([]byte(stdout), &review); err != nil {
		t.Fatalf("decode review: %v", err)
	}
	return review
}

func runSecretRetirementPrepare(
	t *testing.T,
	name string,
) (int, string, string) {
	t.Helper()
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"credentials", "secret-retire", "prepare", name},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)
	return exitCode, stdout.String(), stderr.String()
}

func applySecretRetirement(
	t *testing.T,
	review secretRetirementReviewContract,
) (int, string, string) {
	t.Helper()
	payload, err := json.Marshal(review.ApplyRequest)
	if err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{
			"credentials", "secret-retire", "apply",
			"--confirm", review.ExpectedReview,
		},
		bytes.NewReader(payload),
		&stdout,
		&stderr,
	)
	return exitCode, stdout.String(), stderr.String()
}

func writeOpenCodeSecretRegistry(t *testing.T, config, name string) {
	t.Helper()
	target := filepath.Join(
		config,
		"opencode",
		"opencode.json.mainframe-mcp.json",
	)
	if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
		t.Fatal(err)
	}
	content := `{"version":1,"servers":{"context7":{` +
		`"format":"opencode-file-secret-v1",` +
		`"profile":"remote-api-key",` +
		`"secret_backend":"environment",` +
		`"secret_reference":"` + name + `",` +
		`"entry":{"type":"remote","url":"https://example.test"},` +
		`"secret_file_sha256":"` + strings.Repeat("a", 64) + `"}}}`
	if err := os.WriteFile(target, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}
