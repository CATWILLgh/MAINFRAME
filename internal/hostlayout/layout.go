package hostlayout

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type Environment struct {
	LookupEnv   func(string) (string, bool)
	UserHomeDir func() (string, error)
	GOOS        string
}

type Layout struct {
	source  string
	state   string
	data    string
	targets map[domain.RootID]string
}

func Resolve(environment Environment, source string) (Layout, error) {
	if err := validateEnvironment(environment); err != nil {
		return Layout{}, err
	}
	if err := validateAbsolutePath("source", source); err != nil {
		return Layout{}, err
	}
	home, err := resolveHome(environment)
	if err != nil {
		return Layout{}, err
	}
	codex, err := overrideOrDefault(environment, "CODEX_HOME", filepath.Join(home, ".codex"))
	if err != nil {
		return Layout{}, err
	}
	config, err := overrideOrDefault(environment, "XDG_CONFIG_HOME", filepath.Join(home, ".config"))
	if err != nil {
		return Layout{}, err
	}
	state, err := overrideOrDefault(environment, "XDG_STATE_HOME", filepath.Join(home, ".local", "state"))
	if err != nil {
		return Layout{}, err
	}
	data, err := overrideOrDefault(environment, "XDG_DATA_HOME", filepath.Join(home, ".local", "share"))
	if err != nil {
		return Layout{}, err
	}
	return Layout{
		source: source,
		state:  filepath.Join(state, "mainframe"),
		data:   filepath.Join(data, "mainframe"),
		targets: map[domain.RootID]string{
			domain.RootHome:              home,
			domain.RootClaudeConfig:      filepath.Join(home, ".claude"),
			domain.RootCodexConfig:       codex,
			domain.RootOpenCodeConfig:    filepath.Join(config, "opencode"),
			domain.RootAntigravityConfig: filepath.Join(home, ".gemini", "config"),
			domain.RootAntigravityData:   filepath.Join(home, ".gemini", "antigravity"),
			domain.RootCredentialsConfig: filepath.Join(config, "credentials"),
			domain.RootUserBin:           filepath.Join(home, ".local", "bin"),
		},
	}, nil
}

func (layout Layout) Source() string {
	return layout.source
}

func (layout Layout) State() string {
	return layout.state
}

func (layout Layout) Data() string {
	return layout.data
}

func (layout Layout) Targets() map[domain.RootID]string {
	targets := make(map[domain.RootID]string, len(layout.targets))
	for root, target := range layout.targets {
		targets[root] = target
	}
	return targets
}

func validateEnvironment(environment Environment) error {
	if environment.LookupEnv == nil {
		return fmt.Errorf("LookupEnv must not be nil")
	}
	if environment.UserHomeDir == nil {
		return fmt.Errorf("UserHomeDir must not be nil")
	}
	if environment.GOOS != "darwin" && environment.GOOS != "linux" {
		return fmt.Errorf("unsupported operating system %q", environment.GOOS)
	}
	return nil
}

func resolveHome(environment Environment) (string, error) {
	if home, exists := environment.LookupEnv("HOME"); exists && home != "" {
		if err := validateAbsolutePath("HOME", home); err != nil {
			return "", err
		}
		return home, nil
	}
	home, err := environment.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve user home: %w", err)
	}
	if err := validateAbsolutePath("home", home); err != nil {
		return "", err
	}
	return home, nil
}

func overrideOrDefault(environment Environment, name, fallback string) (string, error) {
	value, exists := environment.LookupEnv(name)
	if !exists || value == "" {
		return fallback, nil
	}
	if err := validateAbsolutePath(name, value); err != nil {
		return "", err
	}
	return value, nil
}

func validateAbsolutePath(name, value string) error {
	if value == "" || strings.ContainsRune(value, '\x00') || !filepath.IsAbs(value) || filepath.Clean(value) != value {
		return fmt.Errorf("invalid %s path %q: must be absolute, clean, and NUL-free", name, value)
	}
	return nil
}
