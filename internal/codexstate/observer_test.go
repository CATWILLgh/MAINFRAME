package codexstate

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestObserverRequiresExactTrustedHookSet(t *testing.T) {
	releaseRoot, resource, target := hookFixture(t)
	trusted := []Hook{
		hook(target, "preToolUse", "first", TrustTrusted),
		hook(target, "preToolUse", "second", TrustManaged),
	}
	tests := map[string]struct {
		hooks  []Hook
		status configuration.ExternalStatus
	}{
		"trusted": {
			hooks: trusted, status: configuration.ExternalSatisfied,
		},
		"untrusted": {
			hooks: []Hook{
				hook(target, "preToolUse", "first", TrustUntrusted),
				hook(target, "preToolUse", "second", TrustManaged),
			},
			status: configuration.ExternalActionRequired,
		},
		"modified": {
			hooks: []Hook{
				hook(target, "preToolUse", "first", TrustModified),
				hook(target, "preToolUse", "second", TrustManaged),
			},
			status: configuration.ExternalActionRequired,
		},
		"disabled": {
			hooks: []Hook{
				disabledHook(target, "preToolUse", "first"),
				hook(target, "preToolUse", "second", TrustManaged),
			},
			status: configuration.ExternalActionRequired,
		},
		"empty": {
			status: configuration.ExternalActionRequired,
		},
		"partial": {
			hooks:  []Hook{hook(target, "preToolUse", "first", TrustTrusted)},
			status: configuration.ExternalActionRequired,
		},
		"unexpected": {
			hooks:  append(trusted, hook(target, "stop", "extra", TrustTrusted)),
			status: configuration.ExternalActionRequired,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			client := &fakeClient{listing: Listing{Hooks: test.hooks}}
			observer, err := NewObserver(
				releaseRoot,
				"/workspace/one",
				map[domain.RootID]string{domain.RootCodexConfig: filepath.Dir(target)},
				[]releasecontract.Resource{resource},
				client,
			)
			if err != nil {
				t.Fatalf("NewObserver() error = %v", err)
			}
			got := observer.Observe(resource)
			if got.Status != test.status {
				t.Fatalf("status = %q, want %q", got.Status, test.status)
			}
		})
	}
}

func TestObserverFailsClosedForWarningsErrorsAndUnavailableClient(t *testing.T) {
	releaseRoot, resource, target := hookFixture(t)
	tests := map[string]struct {
		listing Listing
		err     error
		status  configuration.ExternalStatus
	}{
		"warning": {
			listing: Listing{Hooks: []Hook{
				hook(target, "preToolUse", "first", TrustTrusted),
				hook(target, "preToolUse", "second", TrustTrusted),
			}, Warnings: []string{"loader warning"}},
			status: configuration.ExternalFailed,
		},
		"loader error": {
			listing: Listing{Errors: []HookError{{
				Path: "/tmp/hooks.json", Message: "invalid hook",
			}}},
			status: configuration.ExternalFailed,
		},
		"missing Codex": {
			err:    ErrUnavailable,
			status: configuration.ExternalUnavailable,
		},
		"protocol failure": {
			err:    errors.New("invalid response"),
			status: configuration.ExternalFailed,
		},
		"unknown trust state": {
			listing: Listing{Hooks: []Hook{
				hook(target, "preToolUse", "first", "future"),
				hook(target, "preToolUse", "second", TrustTrusted),
			}},
			status: configuration.ExternalFailed,
		},
		"inconsistent managed state": {
			listing: Listing{Hooks: []Hook{
				inconsistentManagedHook(target, "preToolUse", "first"),
				hook(target, "preToolUse", "second", TrustTrusted),
			}},
			status: configuration.ExternalFailed,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			observer, err := NewObserver(
				releaseRoot,
				"/workspace",
				map[domain.RootID]string{domain.RootCodexConfig: filepath.Dir(target)},
				[]releasecontract.Resource{resource},
				&fakeClient{listing: test.listing, err: test.err},
			)
			if err != nil {
				t.Fatalf("NewObserver() error = %v", err)
			}
			if got := observer.Observe(resource); got.Status != test.status {
				t.Fatalf("status = %q, want %q", got.Status, test.status)
			}
		})
	}
}

func TestObserverUsesWorkingDirectoryOnlyAsInspectionContext(t *testing.T) {
	releaseRoot, resource, target := hookFixture(t)
	hooks := []Hook{
		hook(target, "preToolUse", "first", TrustTrusted),
		hook(target, "preToolUse", "second", TrustTrusted),
	}
	for _, cwd := range []string{"/workspace/one", "/workspace/two"} {
		client := &fakeClient{listing: Listing{Hooks: hooks}}
		observer, err := NewObserver(
			releaseRoot,
			cwd,
			map[domain.RootID]string{domain.RootCodexConfig: filepath.Dir(target)},
			[]releasecontract.Resource{resource},
			client,
		)
		if err != nil {
			t.Fatalf("NewObserver() error = %v", err)
		}
		if got := observer.Observe(resource); got.Status != configuration.ExternalSatisfied {
			t.Fatalf("cwd %q status = %q", cwd, got.Status)
		}
		if client.cwd != cwd {
			t.Fatalf("client cwd = %q, want %q", client.cwd, cwd)
		}
	}
}

func hookFixture(t *testing.T) (string, releasecontract.Resource, string) {
	t.Helper()
	root := t.TempDir()
	source := filepath.Join(root, "bundles/codex/hooks.json")
	if err := os.MkdirAll(filepath.Dir(source), 0o755); err != nil {
		t.Fatalf("mkdir source: %v", err)
	}
	raw := `{"hooks":{"PreToolUse":[{"matcher":".*","hooks":[` +
		`{"type":"command","command":"first","async":false},` +
		`{"type":"command","command":"second","async":false}]}]}}`
	if err := os.WriteFile(source, []byte(raw), 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	resource := releasecontract.Resource{
		ID:          "codex.hook-trust",
		ComponentID: domain.ComponentCodex,
		Strategy:    releasecontract.StrategyManualAction,
		SourcePath:  "bundles/codex/hooks.json",
		Target: domain.Location{
			Root: domain.RootCodexConfig,
			Path: "hooks.json",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
		ExternalState: &releasecontract.ExternalStateDescriptor{
			Kind: releasecontract.ExternalStateCodexHookTrust,
		},
	}
	return root, resource, filepath.Join(root, "host/hooks.json")
}

func hook(source, event, command string, trust TrustStatus) Hook {
	matcher := ".*"
	return Hook{
		SourcePath:  source,
		EventName:   event,
		HandlerType: "command",
		Matcher:     &matcher,
		Command:     command,
		Enabled:     true,
		IsManaged:   trust == TrustManaged,
		TrustStatus: trust,
	}
}

func disabledHook(source, event, command string) Hook {
	result := hook(source, event, command, TrustTrusted)
	result.Enabled = false
	return result
}

func inconsistentManagedHook(source, event, command string) Hook {
	result := hook(source, event, command, TrustManaged)
	result.IsManaged = false
	return result
}

type fakeClient struct {
	listing Listing
	err     error
	cwd     string
}

func (client *fakeClient) ListHooks(_ context.Context, cwd string) (Listing, error) {
	client.cwd = cwd
	return client.listing, client.err
}
