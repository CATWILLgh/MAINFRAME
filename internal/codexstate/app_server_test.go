package codexstate

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDecodeHooksListRequiresExactContext(t *testing.T) {
	result := json.RawMessage(`{"data":[{
		"cwd":"/workspace",
		"hooks":[{
			"sourcePath":"/home/user/.codex/hooks.json",
			"eventName":"stop",
			"handlerType":"command",
			"command":"true",
			"enabled":true,
			"isManaged":false,
			"trustStatus":"trusted"
		}],
		"warnings":[],
		"errors":[]
	}]}`)
	id := hooksListRequestID
	listing, err := decodeHooksList(
		rpcEnvelope{ID: &id, Result: result},
		"/workspace",
	)
	if err != nil || len(listing.Hooks) != 1 {
		t.Fatalf("decodeHooksList() = %#v, %v", listing, err)
	}
	if _, err := decodeHooksList(
		rpcEnvelope{ID: &id, Result: result},
		"/other",
	); err == nil {
		t.Fatal("mismatched context was accepted")
	}
}

func TestDecodeHooksListRequiresCompleteProtocolRows(t *testing.T) {
	id := hooksListRequestID
	valid := `{"data":[{
		"cwd":"/workspace",
		"hooks":[],
		"warnings":[],
		"errors":[{"path":"/tmp/hooks.json","message":"invalid hook"}]
	}]}`
	listing, err := decodeHooksList(
		rpcEnvelope{ID: &id, Result: json.RawMessage(valid)},
		"/workspace",
	)
	if err != nil || len(listing.Errors) != 1 {
		t.Fatalf("decode real error shape = %#v, %v", listing, err)
	}
	for _, incomplete := range []string{
		`{"data":[{"cwd":"/workspace","hooks":[],"errors":[]}]}`,
		`{"data":[{"cwd":"/workspace","hooks":[],"warnings":[]}]}`,
		`{"data":[{"cwd":"/workspace","warnings":[],"errors":[]}]}`,
		`{"data":[{
			"cwd":"/workspace",
			"hooks":[{
				"sourcePath":"/home/user/.codex/hooks.json",
				"eventName":"stop",
				"handlerType":"command",
				"command":"true",
				"enabled":true,
				"trustStatus":"trusted"
			}],
			"warnings":[],
			"errors":[]
		}]}`,
		`{}`,
	} {
		if _, err := decodeHooksList(
			rpcEnvelope{ID: &id, Result: json.RawMessage(incomplete)},
			"/workspace",
		); err == nil {
			t.Fatalf("incomplete hooks/list row was accepted: %s", incomplete)
		}
	}
}

func TestAppServerClientReportsMissingCodexAsUnavailable(t *testing.T) {
	client := AppServerClient{Binary: "mainframe-test-codex-does-not-exist"}
	_, err := client.ListHooks(context.Background(), "/workspace")
	if !errors.Is(err, ErrUnavailable) {
		t.Fatalf("ListHooks() error = %v", err)
	}
}

func TestAppServerClientHonorsInspectionDeadline(t *testing.T) {
	binary := filepath.Join(t.TempDir(), "codex")
	if err := os.WriteFile(binary, []byte("#!/bin/sh\nsleep 10\n"), 0o700); err != nil {
		t.Fatalf("write fake Codex: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	started := time.Now()
	_, err := (AppServerClient{Binary: binary}).ListHooks(ctx, "/workspace")
	if err == nil {
		t.Fatal("timed-out Codex inspection succeeded")
	}
	if elapsed := time.Since(started); elapsed > time.Second {
		t.Fatalf("deadline took %s", elapsed)
	}
}
