package codexstate

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const observationTimeout = 5 * time.Second

type Observer struct {
	cwd      string
	client   Client
	expected map[string]expectedResource
}

type expectedResource struct {
	sourcePath string
	hooks      map[semanticHook]int
}

type semanticHook struct {
	event      string
	handler    string
	matcher    string
	hasMatcher bool
	command    string
}

type hookManifest struct {
	Hooks map[string][]hookGroup `json:"hooks"`
}

type hookGroup struct {
	Matcher *string       `json:"matcher,omitempty"`
	Hooks   []hookHandler `json:"hooks"`
}

type hookHandler struct {
	Type           string  `json:"type"`
	Command        string  `json:"command"`
	CommandWindows *string `json:"commandWindows,omitempty"`
	Timeout        *uint64 `json:"timeout,omitempty"`
	Async          bool    `json:"async,omitempty"`
	StatusMessage  *string `json:"statusMessage,omitempty"`
}

func NewObserver(
	releaseRoot string,
	cwd string,
	roots map[domain.RootID]string,
	resources []releasecontract.Resource,
	client Client,
) (Observer, error) {
	if client == nil {
		return Observer{}, fmt.Errorf("Codex hook client must not be nil")
	}
	if !cleanAbsolute(releaseRoot) || !cleanAbsolute(cwd) {
		return Observer{}, fmt.Errorf("Codex hook observer paths must be absolute and clean")
	}
	expected := make(map[string]expectedResource)
	for _, resource := range resources {
		if resource.ExternalState == nil {
			continue
		}
		loaded, err := loadExpectedResource(releaseRoot, roots, resource)
		if err != nil {
			return Observer{}, fmt.Errorf(
				"load external state resource %q: %w",
				resource.ID,
				err,
			)
		}
		expected[resource.ID] = loaded
	}
	return Observer{cwd: cwd, client: client, expected: expected}, nil
}

func (observer Observer) Observe(
	resource releasecontract.Resource,
) configuration.ExternalObservation {
	expected, exists := observer.expected[resource.ID]
	if !exists {
		return external(configuration.ExternalFailed)
	}
	ctx, cancel := context.WithTimeout(context.Background(), observationTimeout)
	defer cancel()
	listing, err := observer.client.ListHooks(ctx, observer.cwd)
	if err != nil {
		if errors.Is(err, ErrUnavailable) {
			return external(configuration.ExternalUnavailable)
		}
		return external(configuration.ExternalFailed)
	}
	return classifyListing(expected, listing)
}

func loadExpectedResource(
	releaseRoot string,
	roots map[domain.RootID]string,
	resource releasecontract.Resource,
) (expectedResource, error) {
	if resource.ExternalState.Kind != releasecontract.ExternalStateCodexHookTrust {
		return expectedResource{}, fmt.Errorf("unsupported external state kind")
	}
	root, exists := roots[resource.Target.Root]
	if !exists || !cleanAbsolute(root) {
		return expectedResource{}, fmt.Errorf("external target root is unavailable")
	}
	source := filepath.Join(
		releaseRoot,
		filepath.FromSlash(string(resource.SourcePath)),
	)
	payload, err := os.ReadFile(source)
	if err != nil {
		return expectedResource{}, fmt.Errorf("read desired hooks: %w", err)
	}
	hooks, err := parseExpectedHooks(payload)
	if err != nil {
		return expectedResource{}, err
	}
	if len(hooks) == 0 {
		return expectedResource{}, fmt.Errorf("desired hook set is empty")
	}
	return expectedResource{
		sourcePath: filepath.Join(
			root,
			filepath.FromSlash(string(resource.Target.Path)),
		),
		hooks: hooks,
	}, nil
}

func parseExpectedHooks(payload []byte) (map[semanticHook]int, error) {
	if _, err := jsondocument.Parse(payload); err != nil {
		return nil, fmt.Errorf("parse desired hooks: %w", err)
	}
	var manifest hookManifest
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&manifest); err != nil {
		return nil, fmt.Errorf("decode desired hooks: %w", err)
	}
	result := make(map[semanticHook]int)
	for event, groups := range manifest.Hooks {
		normalized, exists := normalizedEvents[event]
		if !exists {
			return nil, fmt.Errorf("unsupported desired hook event %q", event)
		}
		for _, group := range groups {
			for _, handler := range group.Hooks {
				if handler.Type != "command" || handler.Command == "" {
					return nil, fmt.Errorf("unsupported desired hook handler")
				}
				key := semanticHook{
					event:   normalized,
					handler: handler.Type,
					command: handler.Command,
				}
				if group.Matcher != nil {
					key.matcher, key.hasMatcher = *group.Matcher, true
				}
				result[key]++
			}
		}
	}
	return result, nil
}

func classifyListing(
	expected expectedResource,
	listing Listing,
) configuration.ExternalObservation {
	if len(listing.Warnings) != 0 || len(listing.Errors) != 0 {
		return external(configuration.ExternalFailed)
	}
	actual := make(map[semanticHook]int)
	var relevant []Hook
	for _, hook := range listing.Hooks {
		if filepath.Clean(hook.SourcePath) != expected.sourcePath {
			continue
		}
		key := semanticHook{
			event:   hook.EventName,
			handler: hook.HandlerType,
			command: hook.Command,
		}
		if hook.Matcher != nil {
			key.matcher, key.hasMatcher = *hook.Matcher, true
		}
		actual[key]++
		relevant = append(relevant, hook)
	}
	if !equalHookSets(expected.hooks, actual) {
		return external(configuration.ExternalActionRequired)
	}
	for _, hook := range relevant {
		if !hook.Enabled {
			return external(configuration.ExternalActionRequired)
		}
		switch hook.TrustStatus {
		case TrustTrusted:
			if hook.IsManaged {
				return external(configuration.ExternalFailed)
			}
		case TrustManaged:
			if !hook.IsManaged {
				return external(configuration.ExternalFailed)
			}
		case TrustUntrusted, TrustModified:
			return external(configuration.ExternalActionRequired)
		default:
			return external(configuration.ExternalFailed)
		}
	}
	return external(configuration.ExternalSatisfied)
}

func equalHookSets(left, right map[semanticHook]int) bool {
	if len(left) == 0 || len(left) != len(right) {
		return false
	}
	for hook, count := range left {
		if right[hook] != count {
			return false
		}
	}
	return true
}

func external(status configuration.ExternalStatus) configuration.ExternalObservation {
	return configuration.ExternalObservation{Status: status}
}

func cleanAbsolute(value string) bool {
	return value != "" && filepath.IsAbs(value) && filepath.Clean(value) == value
}

var normalizedEvents = map[string]string{
	"PermissionRequest": "permissionRequest",
	"PostCompact":       "postCompact",
	"PostToolUse":       "postToolUse",
	"PreCompact":        "preCompact",
	"PreToolUse":        "preToolUse",
	"SessionStart":      "sessionStart",
	"Stop":              "stop",
	"SubagentStart":     "subagentStart",
	"SubagentStop":      "subagentStop",
	"UserPromptSubmit":  "userPromptSubmit",
}
