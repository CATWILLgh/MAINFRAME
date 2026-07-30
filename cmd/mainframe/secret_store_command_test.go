package main

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"
)

func TestHiddenSecretStoreCommandSupportsPublicAndRetirementOperations(t *testing.T) {
	t.Setenv("XDG_CONFIG_HOME", t.TempDir())
	var output, errorOutput bytes.Buffer

	if code := run(
		[]string{"_secret-store", "create-stdin", "API_KEY"},
		strings.NewReader("stored value"), &output, &errorOutput,
	); code != 0 {
		t.Fatalf("create exit = %d, stderr = %q", code, errorOutput.String())
	}
	if output.Len() != 0 {
		t.Fatalf("create output = %q", output.String())
	}

	output.Reset()
	errorOutput.Reset()
	if code := run(
		[]string{"_secret-store", "get", "API_KEY"},
		strings.NewReader(""), &output, &errorOutput,
	); code != 0 || output.String() != "stored value" {
		t.Fatalf("get exit/output = %d/%q, stderr = %q", code, output.String(), errorOutput.String())
	}

	output.Reset()
	errorOutput.Reset()
	if code := run(
		[]string{"_secret-store", "prepare-retire", "API_KEY"},
		strings.NewReader(""), &output, &errorOutput,
	); code != 0 {
		t.Fatalf("prepare exit = %d, stderr = %q", code, errorOutput.String())
	}
	generation := strings.TrimSpace(output.String())
	if generation == "" || strings.Contains(generation, "stored value") {
		t.Fatalf("unsafe generation %q", generation)
	}

	output.Reset()
	errorOutput.Reset()
	if code := run(
		[]string{"_secret-store", "del-if-generation", "API_KEY", generation},
		strings.NewReader(""), &output, &errorOutput,
	); code != 0 || output.Len() != 0 {
		t.Fatalf("delete exit/output = %d/%q, stderr = %q", code, output.String(), errorOutput.String())
	}
}

func TestSecretStoreCommandIsHiddenFromCapabilities(t *testing.T) {
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(t.TempDir(), "config"))
	var output, errorOutput bytes.Buffer
	if code := run(
		[]string{"capabilities", "--json"}, strings.NewReader(""), &output, &errorOutput,
	); code != 0 {
		t.Fatalf("capabilities exit = %d, stderr = %q", code, errorOutput.String())
	}
	if strings.Contains(output.String(), "_secret-store") {
		t.Fatal("internal secret command was published")
	}
}
