//go:build darwin || linux

package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func assertCredentialMCPApplyState(
	t *testing.T,
	home string,
	config string,
	expectedSecret string,
) {
	t.Helper()
	instances := filepath.Join(
		config,
		"credentials",
		"mainframe",
		"instances.json",
	)
	info, err := os.Stat(instances)
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("credential state = %#v, %v", info, err)
	}
	openCodePath := filepath.Join(config, "opencode", "opencode.json")
	payload, err := os.ReadFile(openCodePath)
	if err != nil {
		t.Fatalf("read OpenCode config: %v", err)
	}
	content := string(payload)
	if !strings.Contains(content, "{file:mainframe/secrets/context7-api-key}") ||
		strings.Contains(content, "CONTEXT7_HOME_KEY") ||
		strings.Contains(content, "raw-secret-must-not-appear") {
		t.Fatalf("OpenCode credential projection = %s", content)
	}
	assertOpenCodePrivateCredential(t, config, expectedSecret)
	assertForeignCredentialAdaptersAbsent(t, home)
}

func assertOpenCodePrivateCredential(
	t *testing.T,
	config string,
	expectedSecret string,
) {
	t.Helper()
	secretPath := filepath.Join(
		config,
		"opencode",
		"mainframe",
		"secrets",
		"context7-api-key",
	)
	secretInfo, err := os.Stat(secretPath)
	if err != nil || secretInfo.Mode().Perm() != 0o600 {
		t.Fatalf("OpenCode private credential file is unavailable")
	}
	secretPayload, err := os.ReadFile(secretPath)
	if err != nil || string(secretPayload) != expectedSecret {
		t.Fatalf("OpenCode private credential file content is incorrect")
	}
	for _, directory := range []string{
		filepath.Dir(secretPath),
		filepath.Dir(filepath.Dir(secretPath)),
	} {
		info, statErr := os.Stat(directory)
		if statErr != nil || info.Mode().Perm() != 0o700 {
			t.Fatalf("OpenCode private credential directory is unavailable")
		}
	}
}

func assertForeignCredentialAdaptersAbsent(t *testing.T, home string) {
	t.Helper()
	for _, path := range []string{
		filepath.Join(home, ".claude"),
		filepath.Join(home, ".codex"),
	} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("unselected config root exists: %s (%v)", path, err)
		}
	}
}

func assertCredentialMCPKeylessState(t *testing.T, config string) {
	t.Helper()
	payload, err := os.ReadFile(filepath.Join(config, "opencode", "opencode.json"))
	if err != nil {
		t.Fatal(err)
	}
	content := string(payload)
	if strings.Contains(content, "CONTEXT7_API_KEY") ||
		!strings.Contains(content, "https://mcp.context7.com/mcp") {
		t.Fatalf("OpenCode keyless projection is incorrect")
	}
	assertCredentialMCPSecretAbsent(t, config)
}

func assertCredentialMCPRemovedState(t *testing.T, config string) {
	t.Helper()
	payload, err := os.ReadFile(filepath.Join(config, "opencode", "opencode.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(payload), "context7") {
		t.Fatalf("OpenCode removed projection remains configured")
	}
	assertCredentialMCPSecretAbsent(t, config)
}

func assertCredentialMCPSecretAbsent(t *testing.T, config string) {
	t.Helper()
	path := filepath.Join(
		config,
		"opencode",
		"mainframe",
		"secrets",
		"context7-api-key",
	)
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("OpenCode private credential file still exists")
	}
}
