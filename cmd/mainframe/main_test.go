package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestRunWithoutArgumentsLaunchesReadOnlyPreview(t *testing.T) {
	var stdout, stderr bytes.Buffer
	called := false
	launcher := func(input io.Reader, output io.Writer) error {
		called = true
		if input == nil || output != &stdout {
			t.Fatal("launcher did not receive command IO")
		}
		return nil
	}

	exitCode := runWithPreview(nil, strings.NewReader(""), &stdout, &stderr, launcher)
	if exitCode != 0 || !called {
		t.Fatalf("exit code = %d, called = %v, stderr = %q", exitCode, called, stderr.String())
	}
}

func TestRunReportsPreviewStartupFailure(t *testing.T) {
	var stdout, stderr bytes.Buffer
	launcher := func(io.Reader, io.Writer) error {
		return errors.New("source root unavailable")
	}

	exitCode := runWithPreview(nil, strings.NewReader(""), &stdout, &stderr, launcher)
	if exitCode != 1 || !strings.Contains(stderr.String(), "source root unavailable") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestPlanCommandDoesNotLaunchPreview(t *testing.T) {
	usePlanRelease(t)
	input := `{"desired":{"components":[]},"observed":{"components":[]}}`
	var stdout, stderr bytes.Buffer
	launcher := func(io.Reader, io.Writer) error {
		t.Fatal("preview launched for plan command")
		return nil
	}

	exitCode := runWithPreview(
		[]string{"plan"}, strings.NewReader(input), &stdout, &stderr, launcher,
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func TestRunPlanJSONContract(t *testing.T) {
	usePlanRelease(t)
	input := `{"desired":{"components":[]},"observed":{"components":[{"id":"codex","artifacts":[{"location":{"root":"codex-config","path":"AGENTS.md"},"ownership":"foreign"}]}]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var got domain.Plan
	if err := json.Unmarshal(stdout.Bytes(), &got); err != nil {
		t.Fatalf("decode stdout: %v; output = %q", err, stdout.String())
	}
	if len(got.Operations) != 1 || got.Operations[0].Kind != domain.OperationConflict {
		t.Fatalf("unexpected plan: %#v", got)
	}
	if got.Operations[0].SourcePath != "" {
		t.Fatalf("conflict source path = %q, want empty", got.Operations[0].SourcePath)
	}
	var contract map[string]json.RawMessage
	if err := json.Unmarshal(stdout.Bytes(), &contract); err != nil {
		t.Fatalf("decode JSON contract: %v", err)
	}
	if _, exists := contract["configuration"]; exists {
		t.Fatalf("plan JSON unexpectedly exposes configuration: %s", stdout.String())
	}
	for _, internalField := range []string{"release_id", "index_sha256", "unit_id"} {
		if strings.Contains(stdout.String(), `"`+internalField+`"`) {
			t.Fatalf("plan JSON unexpectedly exposes %q: %s", internalField, stdout.String())
		}
	}
}

func TestRunPlanDoesNotExposeOwnershipImplementationDetails(t *testing.T) {
	usePlanRelease(t)
	input := `{"desired":{"components":["codex"]},"observed":{"components":[{"id":"codex","artifacts":[{"location":{"root":"codex-config","path":"AGENTS.md"},"unit_id":"codex.instructions","ownership":"managed_previous","raw_target":"/old/AGENTS.md","link_device":7,"link_inode":8,"link_birth_seconds":9,"link_birth_nanoseconds":10}]}]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	for _, internalField := range []string{
		"unit_id", "raw_target", "link_device", "link_inode",
		"link_birth_seconds", "link_birth_nanoseconds",
	} {
		if strings.Contains(stdout.String(), `"`+internalField+`"`) {
			t.Fatalf("plan JSON unexpectedly exposes %q: %s", internalField, stdout.String())
		}
	}
}

func TestRunRejectsUnknownJSONFields(t *testing.T) {
	input := `{"desired":{"components":[]},"observed":{"components":[]},"surprise":true}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "unknown field") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout should be empty, got %q", stdout.String())
	}
}

func TestRunRejectsTrailingJSONValue(t *testing.T) {
	input := `{"desired":{"components":[]},"observed":{"components":[]}} {}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "single JSON request") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func TestRunRejectsDuplicateJSONKeys(t *testing.T) {
	inputs := []string{
		`{"desired":{"components":["codex"]},"desired":{"components":[]},"observed":{"components":[]}}`,
		`{"desired":{"components":[],"components":["codex"]},"observed":{"components":[]}}`,
		`{"desired":{"components":[]},"observed":{"components":[{"id":"codex","id":"claude-code","artifacts":[]}]}}`,
	}
	for _, input := range inputs {
		var stdout, stderr bytes.Buffer
		exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
		if exitCode == 0 || !strings.Contains(stderr.String(), "duplicate JSON key") {
			t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
		}
		if stdout.Len() != 0 {
			t.Fatalf("stdout should be empty, got %q", stdout.String())
		}
	}
}

func TestRunRejectsOversizedRequest(t *testing.T) {
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"plan"},
		strings.NewReader(strings.Repeat(" ", maxPlanRequestBytes+1)),
		&stdout,
		&stderr,
	)
	if exitCode == 0 || !strings.Contains(stderr.String(), "request exceeds") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout should be empty, got %q", stdout.String())
	}
}

func TestRunRejectsUnknownCommand(t *testing.T) {
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"apply"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "unknown command") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func TestRunRejectsUnknownDesiredComponent(t *testing.T) {
	usePlanRelease(t)
	input := `{"desired":{"components":["unknown"]},"observed":{"components":[]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "unknown component") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func TestRunRejectsNullRequest(t *testing.T) {
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader("null"), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "must not be null") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}

func TestRunRejectsUnknownOwnership(t *testing.T) {
	usePlanRelease(t)
	input := `{"desired":{"components":[]},"observed":{"components":[{"id":"codex","artifacts":[{"location":{"root":"codex-config","path":"x"},"ownership":"unknown"}]}]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "invalid ownership") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}
