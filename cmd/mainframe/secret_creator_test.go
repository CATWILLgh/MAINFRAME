package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSecretHelperCreatorSendsValueOnlyThroughStandardInput(t *testing.T) {
	output := filepath.Join(t.TempDir(), "invocation")
	helper := writeSecretCreatorHelper(t, `
printf '%s\n' "$@" > "$OUTPUT.args"
env > "$OUTPUT.env"
cat > "$OUTPUT.stdin"
`)
	t.Setenv("OUTPUT", output)
	value := []byte("test-sensitive-value")

	err := newSecretHelperCreator(helper).CreateSecret(
		"CONTEXT7_HOME_KEY",
		value,
	)

	if err != nil {
		t.Fatalf("CreateSecret() error = %v", err)
	}
	assertFileEquals(t, output+".args", "create-stdin\nCONTEXT7_HOME_KEY\n")
	assertFileEquals(t, output+".stdin", string(value))
	arguments, err := os.ReadFile(output + ".args")
	if err != nil {
		t.Fatal(err)
	}
	environment, err := os.ReadFile(output + ".env")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(arguments), string(value)) ||
		strings.Contains(string(environment), string(value)) {
		t.Fatal("secret value escaped the helper standard input")
	}
}

func TestSecretHelperCreatorRejectsInvalidInputWithoutExecution(t *testing.T) {
	marker := filepath.Join(t.TempDir(), "executed")
	helper := writeSecretCreatorHelper(t, `touch "$MARKER"`)
	t.Setenv("MARKER", marker)
	tests := []struct {
		name      string
		reference string
		value     []byte
	}{
		{name: "invalid reference", reference: "invalid-reference", value: []byte("value")},
		{name: "empty value", reference: "VALID_NAME", value: nil},
		{name: "multiline value", reference: "VALID_NAME", value: []byte("first\nsecond")},
		{name: "nul value", reference: "VALID_NAME", value: []byte{'a', 0, 'b'}},
		{
			name: "oversized value", reference: "VALID_NAME",
			value: make([]byte, secretHelperInputLimit+1),
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := newSecretHelperCreator(helper).
				CreateSecret(test.reference, test.value); err == nil {
				t.Fatal("CreateSecret() accepted invalid input")
			}
		})
	}
	if _, err := os.Stat(marker); !os.IsNotExist(err) {
		t.Fatal("invalid input executed the helper")
	}
}

func TestSecretHelperCreatorDoesNotRelaySensitiveFailureOutput(t *testing.T) {
	helper := writeSecretCreatorHelper(
		t,
		`printf 'test-sensitive-failure' >&2; exit 7`,
	)

	err := newSecretHelperCreator(helper).
		CreateSecret("CONTEXT7_HOME_KEY", []byte("test-sensitive-value"))

	if err == nil || !strings.Contains(err.Error(), "could not be created") {
		t.Fatalf("CreateSecret() error = %v", err)
	}
	if strings.Contains(err.Error(), "test-sensitive") {
		t.Fatal("CreateSecret() relayed helper output or input")
	}
}

func writeSecretCreatorHelper(t *testing.T, body string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "secret")
	content := "#!/bin/sh\nset -eu\n" + body + "\n"
	if err := os.WriteFile(path, []byte(content), 0o700); err != nil {
		t.Fatal(err)
	}
	return path
}

func assertFileEquals(t *testing.T, path, want string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != want {
		t.Fatalf("%s content differs", filepath.Base(path))
	}
}
