package main

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestRunPlanJSONContract(t *testing.T) {
	input := `{"desired":{"components":["claude-code"]},"observed":{"components":[{"id":"codex","artifacts":[{"path":".codex/AGENTS.md","ownership":"managed_exact"}]}]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	var got domain.Plan
	if err := json.Unmarshal(stdout.Bytes(), &got); err != nil {
		t.Fatalf("decode stdout: %v; output = %q", err, stdout.String())
	}
	if len(got.Operations) != 1 || got.Operations[0].Kind != domain.OperationRemove {
		t.Fatalf("unexpected plan: %#v", got)
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
	input := `{"desired":{"components":[]},"observed":{"components":[{"id":"codex","artifacts":[{"path":"x","ownership":"unknown"}]}]}}`
	var stdout, stderr bytes.Buffer

	exitCode := run([]string{"plan"}, strings.NewReader(input), &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "invalid ownership") {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
}
