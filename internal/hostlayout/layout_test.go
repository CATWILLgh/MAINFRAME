package hostlayout_test

import (
	"errors"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
)

func TestResolveUsesOverridesAndReturnsIndependentTargetCopies(t *testing.T) {
	home := filepath.Join(t.TempDir(), "home")
	source := filepath.Join(t.TempDir(), "source")
	codex := filepath.Join(t.TempDir(), "codex")
	config := filepath.Join(t.TempDir(), "config")
	state := filepath.Join(t.TempDir(), "state")
	env := environment(map[string]string{
		"HOME":            home,
		"CODEX_HOME":      codex,
		"XDG_CONFIG_HOME": config,
		"XDG_STATE_HOME":  state,
	}, "/fallback", "linux")

	layout, err := hostlayout.Resolve(env, source)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	want := map[domain.RootID]string{
		domain.RootHome:              home,
		domain.RootClaudeConfig:      filepath.Join(home, ".claude"),
		domain.RootCodexConfig:       codex,
		domain.RootOpenCodeConfig:    filepath.Join(config, "opencode"),
		domain.RootAntigravityConfig: filepath.Join(home, ".gemini", "config"),
		domain.RootAntigravityData:   filepath.Join(home, ".gemini", "antigravity"),
		domain.RootCredentialsConfig: filepath.Join(config, "credentials"),
		domain.RootUserBin:           filepath.Join(home, ".local", "bin"),
	}
	assertTargets(t, layout.Targets(), want)
	if layout.Source() != source {
		t.Fatalf("Source() = %q, want %q", layout.Source(), source)
	}
	if layout.State() != filepath.Join(state, "mainframe") {
		t.Fatalf("State() = %q", layout.State())
	}

	first := layout.Targets()
	first[domain.RootHome] = "/mutated"
	delete(first, domain.RootCodexConfig)
	assertTargets(t, layout.Targets(), want)
	if _, exists := layout.Targets()[domain.RootCommonData]; exists {
		t.Fatal("Targets() unexpectedly contains common-data")
	}
}

func TestResolveFallsBackForMissingOrEmptyEnvironmentValues(t *testing.T) {
	home := filepath.Join(t.TempDir(), "fallback-home")
	source := filepath.Join(t.TempDir(), "source")
	env := environment(map[string]string{
		"HOME":            "",
		"CODEX_HOME":      "",
		"XDG_CONFIG_HOME": "",
		"XDG_STATE_HOME":  "",
	}, home, "darwin")

	layout, err := hostlayout.Resolve(env, source)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	targets := layout.Targets()
	if targets[domain.RootHome] != home {
		t.Fatalf("home = %q, want %q", targets[domain.RootHome], home)
	}
	if targets[domain.RootCodexConfig] != filepath.Join(home, ".codex") {
		t.Fatalf("codex = %q", targets[domain.RootCodexConfig])
	}
	if targets[domain.RootOpenCodeConfig] != filepath.Join(home, ".config", "opencode") {
		t.Fatalf("opencode = %q", targets[domain.RootOpenCodeConfig])
	}
	if targets[domain.RootAntigravityConfig] != filepath.Join(home, ".gemini", "config") {
		t.Fatalf("antigravity config = %q", targets[domain.RootAntigravityConfig])
	}
	if targets[domain.RootAntigravityData] != filepath.Join(home, ".gemini", "antigravity") {
		t.Fatalf("antigravity data = %q", targets[domain.RootAntigravityData])
	}
	if layout.State() != filepath.Join(home, ".local", "state", "mainframe") {
		t.Fatalf("state = %q", layout.State())
	}
}

func TestResolveRejectsUnsupportedOrInvalidInputs(t *testing.T) {
	base := t.TempDir()
	validHome := filepath.Join(base, "home")
	validSource := filepath.Join(base, "source")
	tests := []struct {
		name      string
		env       hostlayout.Environment
		source    string
		wantError string
	}{
		{name: "unsupported OS", env: environment(nil, validHome, "windows"), source: validSource, wantError: "unsupported"},
		{name: "relative source", env: environment(nil, validHome, "linux"), source: "source", wantError: "source"},
		{name: "unclean source", env: environment(nil, validHome, "linux"), source: validSource + string(filepath.Separator) + ".." + string(filepath.Separator) + "source", wantError: "source"},
		{name: "NUL source", env: environment(nil, validHome, "linux"), source: validSource + "\x00x", wantError: "source"},
		{name: "relative HOME", env: environment(map[string]string{"HOME": "home"}, validHome, "linux"), source: validSource, wantError: "HOME"},
		{name: "relative CODEX_HOME", env: environment(map[string]string{"HOME": validHome, "CODEX_HOME": "codex"}, validHome, "linux"), source: validSource, wantError: "CODEX_HOME"},
		{name: "unclean XDG_CONFIG_HOME", env: environment(map[string]string{"HOME": validHome, "XDG_CONFIG_HOME": base + string(filepath.Separator) + "config" + string(filepath.Separator) + ".." + string(filepath.Separator) + "config"}, validHome, "linux"), source: validSource, wantError: "XDG_CONFIG_HOME"},
		{name: "relative XDG_STATE_HOME", env: environment(map[string]string{"HOME": validHome, "XDG_STATE_HOME": "state"}, validHome, "linux"), source: validSource, wantError: "XDG_STATE_HOME"},
		{name: "NUL home fallback", env: environment(nil, validHome+"\x00x", "linux"), source: validSource, wantError: "home"},
		{name: "nil lookup", env: hostlayout.Environment{UserHomeDir: func() (string, error) { return validHome, nil }, GOOS: "linux"}, source: validSource, wantError: "LookupEnv"},
		{name: "nil home lookup", env: hostlayout.Environment{LookupEnv: func(string) (string, bool) { return "", false }, GOOS: "linux"}, source: validSource, wantError: "UserHomeDir"},
		{name: "home lookup error", env: hostlayout.Environment{LookupEnv: func(string) (string, bool) { return "", false }, UserHomeDir: func() (string, error) { return "", errors.New("lookup failed") }, GOOS: "linux"}, source: validSource, wantError: "lookup failed"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := hostlayout.Resolve(test.env, test.source)
			if err == nil || !strings.Contains(err.Error(), test.wantError) {
				t.Fatalf("Resolve() error = %v, want containing %q", err, test.wantError)
			}
		})
	}
}

func environment(values map[string]string, fallbackHome, goos string) hostlayout.Environment {
	return hostlayout.Environment{
		LookupEnv: func(key string) (string, bool) {
			value, exists := values[key]
			return value, exists
		},
		UserHomeDir: func() (string, error) { return fallbackHome, nil },
		GOOS:        goos,
	}
}

func assertTargets(t *testing.T, got, want map[domain.RootID]string) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("len(Targets()) = %d, want %d: %#v", len(got), len(want), got)
	}
	for root, wantPath := range want {
		if got[root] != wantPath {
			t.Errorf("Targets()[%q] = %q, want %q", root, got[root], wantPath)
		}
	}
}
