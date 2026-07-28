package main

import (
	"bytes"
	"encoding/json"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestTopLevelHelpDoesNotLaunchTUI(t *testing.T) {
	for _, args := range [][]string{{"--help"}, {"-h"}, {"help"}} {
		t.Run(strings.Join(args, "_"), func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			launcher := func(io.Reader, io.Writer) error {
				t.Fatal("TUI launched for help")
				return nil
			}

			exitCode := runWithPreview(
				args,
				strings.NewReader(""),
				&stdout,
				&stderr,
				launcher,
			)

			if exitCode != 0 || stderr.Len() != 0 {
				t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
			}
			for _, expected := range []string{
				"MAINFRAME manages",
				"mainframe docs list",
				"mainframe capabilities --json",
				"written only after a final preview and confirmation",
				"Secret values use a separate masked entry and explicit confirmation",
			} {
				if !strings.Contains(stdout.String(), expected) {
					t.Fatalf("help does not contain %q:\n%s", expected, stdout.String())
				}
			}
		})
	}
}

func TestContextualHelpCoversMixedCommandNodes(t *testing.T) {
	tests := []struct {
		args     []string
		expected []string
	}{
		{
			args: []string{"credentials", "--help"},
			expected: []string{
				"mainframe credentials",
				"mainframe credentials legacy-indexes",
				"mainframe credentials uses <name>",
				"mainframe credentials instance review",
			},
		},
		{
			args: []string{"credentials", "instance", "--help"},
			expected: []string{
				"mainframe credentials instance review",
				"mainframe credentials instance apply --confirm <digest>",
			},
		},
		{
			args: []string{"help", "docs"},
			expected: []string{
				"mainframe docs list",
				"mainframe docs show <topic>",
			},
		},
		{
			args: []string{"release", "--help"},
			expected: []string{
				"mainframe release review",
				"mainframe release apply --confirm <digest>",
			},
		},
	}

	for _, test := range tests {
		t.Run(strings.Join(test.args, "_"), func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			exitCode := run(
				test.args,
				strings.NewReader(""),
				&stdout,
				&stderr,
			)

			if exitCode != 0 || stderr.Len() != 0 {
				t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
			}
			for _, expected := range test.expected {
				if !strings.Contains(stdout.String(), expected) {
					t.Fatalf("help does not contain %q:\n%s", expected, stdout.String())
				}
			}
		})
	}
}

func TestUnknownHelpPathFailsWithoutPartialOutput(t *testing.T) {
	var stdout, stderr bytes.Buffer

	exitCode := run(
		[]string{"help", "credentials", "missing"},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)

	if exitCode != 2 || stdout.Len() != 0 {
		t.Fatalf(
			"exit code = %d, stdout = %q, stderr = %q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
	if !strings.Contains(stderr.String(), "unknown help topic") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestEmbeddedDocumentationListAndShow(t *testing.T) {
	t.Setenv("MAINFRAME_RELEASE_ROOT", "/does/not/exist")

	var listOutput, listError bytes.Buffer
	if exitCode := run(
		[]string{"docs", "list"},
		strings.NewReader(""),
		&listOutput,
		&listError,
	); exitCode != 0 {
		t.Fatalf("list exit code = %d, stderr = %q", exitCode, listError.String())
	}
	for _, topic := range []string{
		"overview",
		"adapters-and-mcp",
		"credentials",
		"agent-automation",
	} {
		if !strings.Contains(listOutput.String(), topic) {
			t.Fatalf("documentation list omits %q:\n%s", topic, listOutput.String())
		}
	}

	var showOutput, showError bytes.Buffer
	if exitCode := run(
		[]string{"docs", "show", "agent-automation"},
		strings.NewReader(""),
		&showOutput,
		&showError,
	); exitCode != 0 {
		t.Fatalf("show exit code = %d, stderr = %q", exitCode, showError.String())
	}
	for _, expected := range []string{
		"# Agent automation",
		"mainframe capabilities --json",
		"Never place a secret value",
	} {
		if !strings.Contains(showOutput.String(), expected) {
			t.Fatalf("documentation does not contain %q:\n%s", expected, showOutput.String())
		}
	}
}

func TestDocumentationRejectsUnknownAndTraversalTopics(t *testing.T) {
	for _, topic := range []string{"missing", "../overview", "OVERVIEW"} {
		t.Run(topic, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			exitCode := run(
				[]string{"docs", "show", topic},
				strings.NewReader(""),
				&stdout,
				&stderr,
			)

			if exitCode != 2 || stdout.Len() != 0 {
				t.Fatalf(
					"exit code = %d, stdout = %q, stderr = %q",
					exitCode,
					stdout.String(),
					stderr.String(),
				)
			}
			if !strings.Contains(stderr.String(), "unknown documentation topic") {
				t.Fatalf("stderr = %q", stderr.String())
			}
		})
	}
}

func TestCapabilitiesJSONIsVersionedDeterministicAndReleaseIndependent(t *testing.T) {
	t.Setenv("MAINFRAME_RELEASE_ROOT", "/does/not/exist")

	first := runCapabilitiesForTest(t)
	second := runCapabilitiesForTest(t)
	if first != second {
		t.Fatal("capabilities output is not deterministic")
	}

	var response capabilitiesResponse
	if err := json.Unmarshal([]byte(first), &response); err != nil {
		t.Fatalf("decode capabilities: %v; output = %q", err, first)
	}
	if response.SchemaVersion != 1 ||
		response.Kind != "mainframe-capabilities" ||
		response.Invocation != "mainframe" {
		t.Fatalf("unexpected capability envelope: %#v", response)
	}
	if !reflect.DeepEqual(response.Help, []string{
		"mainframe --help",
		"mainframe help [command ...]",
		"mainframe <command> --help",
	}) {
		t.Fatalf("unexpected help contract: %#v", response.Help)
	}
	if !reflect.DeepEqual(response.Commands, expectedCommandCapabilities()) {
		t.Fatalf("unexpected command capabilities: %#v", response.Commands)
	}
	if !reflect.DeepEqual(
		response.Documentation,
		expectedDocumentationCapabilities(),
	) {
		t.Fatalf(
			"unexpected documentation capabilities: %#v",
			response.Documentation,
		)
	}
	assertCapabilitiesPublicShape(t, first)
}

func TestInformationalCommandsRejectUnexpectedArguments(t *testing.T) {
	for _, args := range [][]string{
		{"capabilities"},
		{"capabilities", "--json", "extra"},
		{"docs"},
		{"docs", "list", "extra"},
	} {
		t.Run(strings.Join(args, "_"), func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			exitCode := run(
				args,
				strings.NewReader(""),
				&stdout,
				&stderr,
			)

			if exitCode != 2 || stdout.Len() != 0 {
				t.Fatalf(
					"exit code = %d, stdout = %q, stderr = %q",
					exitCode,
					stdout.String(),
					stderr.String(),
				)
			}
		})
	}
}

func TestUnknownCommandDoesNotEchoArguments(t *testing.T) {
	const marker = "must-not-appear-in-output"
	var stdout, stderr bytes.Buffer

	exitCode := run(
		[]string{"missing", marker},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)

	if exitCode != 2 ||
		strings.Contains(stdout.String()+stderr.String(), marker) {
		t.Fatalf(
			"exit code = %d, stdout = %q, stderr = %q",
			exitCode,
			stdout.String(),
			stderr.String(),
		)
	}
}

func TestCommandAndDocumentationRegistryIsConsistent(t *testing.T) {
	if err := validateCommandAndDocumentationRegistry(); err != nil {
		t.Fatalf("invalid registry: %v", err)
	}
}

func runCapabilitiesForTest(t *testing.T) string {
	t.Helper()
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"capabilities", "--json"},
		strings.NewReader(""),
		&stdout,
		&stderr,
	)
	if exitCode != 0 || stderr.Len() != 0 {
		t.Fatalf("exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	return stdout.String()
}

func assertCapabilitiesPublicShape(t *testing.T, raw string) {
	t.Helper()
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &envelope); err != nil {
		t.Fatalf("decode capability envelope: %v", err)
	}
	expectedEnvelope := []string{
		"schema_version", "kind", "invocation", "help", "commands", "documentation",
	}
	if len(envelope) != len(expectedEnvelope) {
		t.Fatalf("capability fields = %#v", envelope)
	}
	for _, field := range expectedEnvelope {
		if _, exists := envelope[field]; !exists {
			t.Fatalf("capability envelope omits %q", field)
		}
	}
	var commands []map[string]json.RawMessage
	if err := json.Unmarshal(envelope["commands"], &commands); err != nil {
		t.Fatalf("decode command capabilities: %v", err)
	}
	for _, command := range commands {
		if len(command) != 8 {
			t.Fatalf("command capability exposes unexpected fields: %#v", command)
		}
		for _, internal := range []string{"pattern", "handler", "handler_kind"} {
			if _, exists := command[internal]; exists {
				t.Fatalf("command capability exposes %q", internal)
			}
		}
	}
}

func expectedCommandCapabilities() []commandCapability {
	return []commandCapability{
		{ID: "capabilities", Usage: "mainframe capabilities --json", Summary: "Describe the installed command and documentation contract for agents.", Input: inputNone, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "agent-automation"},
		{ID: "credentials.catalog", Usage: "mainframe credentials", Summary: "List credential definitions and user-owned instances without values.", Input: inputNone, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "credentials"},
		{ID: "credentials.instance.apply", Usage: "mainframe credentials instance apply --confirm <digest>", Summary: "Apply the exact credential-instance change returned by review.", Input: inputJSON, Output: outputJSON, Effect: effectReviewedWrite, Confirmation: confirmationDigest, Documentation: "credentials"},
		{ID: "credentials.instance.review", Usage: "mainframe credentials instance review", Summary: "Review a credential-instance create or edit request.", Input: inputJSON, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "credentials"},
		{ID: "credentials.legacy-indexes", Usage: "mainframe credentials legacy-indexes", Summary: "Inspect legacy credential locations without returning their content.", Input: inputNone, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "credentials"},
		{ID: "credentials.uses", Usage: "mainframe credentials uses <name>", Summary: "List credential-instance roles that reference one secret name.", Input: inputArguments, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "credentials"},
		{ID: "docs.list", Usage: "mainframe docs list", Summary: "List documentation embedded in this executable.", Input: inputNone, Output: outputText, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "overview"},
		{ID: "docs.show", Usage: "mainframe docs show <topic>", Summary: "Print one embedded documentation topic.", Input: inputArguments, Output: outputText, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "overview"},
		{ID: "draft.apply", Usage: "mainframe draft apply --confirm <digest>", Summary: "Apply the exact applicable adapter and MCP draft returned by review.", Input: inputJSON, Output: outputJSON, Effect: effectReviewedWrite, Confirmation: confirmationDigest, Documentation: "agent-automation"},
		{ID: "draft.review", Usage: "mainframe draft review", Summary: "Review a complete desired adapter and MCP draft without applying it.", Input: inputJSON, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "agent-automation"},
		{ID: "plan", Usage: "mainframe plan", Summary: "Build a read-only installation plan from JSON on standard input.", Input: inputJSON, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "agent-automation"},
		{ID: "release.apply", Usage: "mainframe release apply --confirm <digest>", Summary: "Apply the exact launcher activation returned by release review.", Input: inputJSON, Output: outputJSON, Effect: effectReviewedWrite, Confirmation: confirmationDigest, Documentation: "releases"},
		{ID: "release.review", Usage: "mainframe release review", Summary: "Review a local release import or exact cached activation.", Input: inputJSON, Output: outputJSON, Effect: effectReadOnly, Confirmation: confirmationNone, Documentation: "releases"},
		{ID: "tui.open", Usage: "mainframe", Summary: "Open the terminal interface.", Input: inputTerminal, Output: outputTerminal, Effect: effectReviewedWrite, Confirmation: confirmationTerminal, Documentation: "overview"},
	}
}

func expectedDocumentationCapabilities() []documentationCapability {
	return []documentationCapability{
		{ID: "adapters-and-mcp", Title: "Adapters and MCP", Summary: "Adapter isolation and MCP connection management.", Command: "mainframe docs show adapters-and-mcp"},
		{ID: "agent-automation", Title: "Agent automation", Summary: "Machine-readable interfaces for discovery, review, and exact application.", Command: "mainframe docs show agent-automation"},
		{ID: "credentials", Title: "Credentials", Summary: "Service instances, shared secret references, and safe value entry.", Command: "mainframe docs show credentials"},
		{ID: "overview", Title: "Overview", Summary: "How MAINFRAME separates choices, preview, confirmation, and application.", Command: "mainframe docs show overview"},
		{ID: "releases", Title: "Local releases", Summary: "Verified local import, exact activation, switching, and rollback.", Command: "mainframe docs show releases"},
	}
}
