package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSecretHelperResolverReturnsExactValue(t *testing.T) {
	helper := writeSecretResolverHelper(t, `printf 'test-only-value'`)
	value, err := newSecretHelperResolver(helper).ResolveSecret("CONTEXT7_HOME_KEY")
	if err != nil {
		t.Fatalf("ResolveSecret() error = %v", err)
	}
	if value != "test-only-value" {
		t.Fatal("ResolveSecret() did not return the exact helper output")
	}
}

func TestSecretHelperResolverRejectsInvalidReferenceWithoutExecution(t *testing.T) {
	marker := filepath.Join(t.TempDir(), "executed")
	helper := writeSecretResolverHelper(t, `touch "$MARKER"`)
	t.Setenv("MARKER", marker)

	_, err := newSecretHelperResolver(helper).ResolveSecret("invalid-reference")

	if err == nil || !strings.Contains(err.Error(), "reference is invalid") {
		t.Fatalf("ResolveSecret() error = %v", err)
	}
	if _, statErr := os.Stat(marker); !os.IsNotExist(statErr) {
		t.Fatal("invalid secret reference executed the helper")
	}
}

func TestSecretHelperResolverDoesNotRelayHelperFailure(t *testing.T) {
	helper := writeSecretResolverHelper(
		t,
		`printf 'test-only-sensitive-stderr' >&2; exit 7`,
	)

	_, err := newSecretHelperResolver(helper).ResolveSecret("CONTEXT7_HOME_KEY")

	if err == nil || !strings.Contains(err.Error(), "could not be resolved") {
		t.Fatalf("ResolveSecret() error = %v", err)
	}
	if strings.Contains(err.Error(), "test-only-sensitive-stderr") {
		t.Fatal("ResolveSecret() relayed helper stderr")
	}
}

func TestSecretHelperResolverRejectsUnsafeOutput(t *testing.T) {
	tests := []struct {
		name   string
		script string
	}{
		{name: "empty", script: `exit 0`},
		{
			name:   "oversized",
			script: `head -c 70000 /dev/zero | tr '\000' x`,
		},
		{name: "nul", script: `printf 'value\000suffix'`},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			helper := writeSecretResolverHelper(t, test.script)
			_, err := newSecretHelperResolver(helper).
				ResolveSecret("CONTEXT7_HOME_KEY")
			if err == nil || !strings.Contains(err.Error(), "invalid value") {
				t.Fatalf("ResolveSecret() error = %v", err)
			}
		})
	}
}

func writeSecretResolverHelper(t *testing.T, body string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "secret")
	content := "#!/bin/sh\nset -eu\n" + body + "\n"
	if err := os.WriteFile(path, []byte(content), 0o700); err != nil {
		t.Fatal(err)
	}
	return path
}
