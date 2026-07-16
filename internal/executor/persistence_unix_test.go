//go:build unix

package executor

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestOpenUnixStateRejectsUnsafeRootsAndSymlink(t *testing.T) {
	parent := canonicalTempDir(t)
	target := filepath.Join(parent, "target")
	if err := os.Mkdir(target, 0o700); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(parent, "link")
	if err := os.Symlink(target, link); err != nil {
		t.Fatal(err)
	}
	for _, root := range []string{"relative", parent + "/x/../x", "/", link} {
		t.Run(strings.ReplaceAll(root, "/", "_"), func(t *testing.T) {
			state, err := OpenUnixState(root)
			if err == nil {
				state.Close()
				t.Fatalf("expected unsafe root %q to fail", root)
			}
		})
	}
}

func TestOpenUnixStateRejectsSymlinkAncestorAndCreatesPrivateParents(t *testing.T) {
	parent := canonicalTempDir(t)
	realAncestor := filepath.Join(parent, "real")
	if err := os.Mkdir(realAncestor, 0o700); err != nil {
		t.Fatal(err)
	}
	linkAncestor := filepath.Join(parent, "linked")
	if err := os.Symlink(realAncestor, linkAncestor); err != nil {
		t.Fatal(err)
	}
	if state, err := OpenUnixState(filepath.Join(linkAncestor, "state")); err == nil {
		state.Close()
		t.Fatal("followed symbolic-link ancestor")
	}

	root := filepath.Join(parent, "nested", "private", "state")
	state := openTestState(t, root)
	defer state.Close()
	for _, directory := range []string{
		filepath.Join(parent, "nested"),
		filepath.Join(parent, "nested", "private"),
		root,
	} {
		assertMode(t, directory, 0o700)
	}
}

func TestUnixStateUsesPrivateModesAndExclusiveProcessLock(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	first := openTestState(t, root)
	defer first.Close()
	second := openTestState(t, root)
	defer second.Close()

	firstLock, err := first.Lock()
	if err != nil {
		t.Fatalf("first lock: %v", err)
	}
	if _, err := second.Lock(); err == nil {
		t.Fatal("second process lock unexpectedly succeeded")
	}
	if err := firstLock.Unlock(); err != nil {
		t.Fatalf("unlock: %v", err)
	}
	secondLock, err := second.Lock()
	if err != nil {
		t.Fatalf("lock after release: %v", err)
	}
	if err := secondLock.Unlock(); err != nil {
		t.Fatalf("second unlock: %v", err)
	}

	assertMode(t, root, 0o700)
	assertMode(t, filepath.Join(root, lockFileName), 0o600)
}

func TestUnixJournalStoreSavesLoadsAndCleansAtomically(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	defer state.Close()
	journal := journalWith(TransactionInProgress, installJournalStep("one", StepPrepared))

	if err := state.Save(*journal); err != nil {
		t.Fatalf("save: %v", err)
	}
	loaded, err := state.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if loaded == nil || loaded.Steps[0] != journal.Steps[0] {
		t.Fatalf("loaded journal = %#v", loaded)
	}
	assertMode(t, filepath.Join(root, journalFileName), 0o600)
	entries, err := os.ReadDir(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), journalTempPrefix) {
			t.Fatalf("temporary journal leaked: %q", entry.Name())
		}
	}
	if err := state.Cleanup(); err != nil {
		t.Fatalf("cleanup: %v", err)
	}
	if err := state.Cleanup(); err != nil {
		t.Fatalf("missing cleanup: %v", err)
	}
	loaded, err = state.Load()
	if err != nil || loaded != nil {
		t.Fatalf("load after cleanup = %#v, %v", loaded, err)
	}
}

func TestUnixJournalStoreRejectsUntrustedJSON(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	defer state.Close()
	valid := `{"release":{"id":"release","index_sha256":"` + testDigest("digest") +
		`"},"desired":["codex"],"status":"in_progress","plan":{"operations":[]},` +
		`"roots":[],"directories":[],"steps":[]}`
	tests := []struct {
		name    string
		payload string
	}{
		{name: "unknown", payload: strings.Replace(valid, `"steps":[]`, `"steps":[],"unknown":true`, 1)},
		{name: "duplicate", payload: strings.Replace(valid, `"status":"in_progress"`, `"status":"in_progress","status":"committed"`, 1)},
		{name: "missing steps", payload: strings.Replace(valid, `,"steps":[]`, "", 1)},
		{name: "null steps", payload: strings.Replace(valid, `"steps":[]`, `"steps":null`, 1)},
		{name: "trailing", payload: valid + `{}`},
		{name: "oversize", payload: strings.Repeat(" ", maxJournalBytes+1)},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			writeJournalFixture(t, root, []byte(test.payload))
			if _, err := state.Load(); err == nil {
				t.Fatalf("accepted %s journal", test.name)
			}
		})
	}
}

func TestUnixJournalStoreRejectsSymlinkAndLooseMode(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	defer state.Close()
	outside := filepath.Join(t.TempDir(), "outside")
	if err := os.WriteFile(outside, []byte("{}"), 0o600); err != nil {
		t.Fatal(err)
	}
	journalPath := filepath.Join(root, journalFileName)
	if err := os.Symlink(outside, journalPath); err != nil {
		t.Fatal(err)
	}
	if _, err := state.Load(); err == nil {
		t.Fatal("followed journal symlink")
	}
	if err := os.Remove(journalPath); err != nil {
		t.Fatal(err)
	}
	writeJournalFixture(t, root, []byte(`{}`))
	if err := os.Chmod(journalPath, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := state.Load(); err == nil {
		t.Fatal("accepted loosely permissioned journal")
	}
}

func TestUnixJournalStoreRejectsOversizedSave(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	defer state.Close()
	journal := journalWith(TransactionInProgress, installJournalStep("one", StepPrepared))
	journal.Steps[0].After.RawTarget = strings.Repeat("x", maxJournalBytes)

	if err := state.Save(*journal); err == nil {
		t.Fatal("oversized journal save unexpectedly succeeded")
	}
	if _, err := os.Stat(filepath.Join(root, journalFileName)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("oversized save published journal: %v", err)
	}
}

func openTestState(t *testing.T, root string) *UnixState {
	t.Helper()
	state, err := OpenUnixState(root)
	if err != nil {
		t.Fatalf("open state: %v", err)
	}
	return state
}

func writeJournalFixture(t *testing.T, root string, payload []byte) {
	t.Helper()
	path := filepath.Join(root, journalFileName)
	if err := os.WriteFile(path, payload, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(path, 0o600); err != nil {
		t.Fatal(err)
	}
}

func assertMode(t *testing.T, path string, want os.FileMode) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := info.Mode().Perm(); got != want {
		t.Fatalf("%s mode = %#o, want %#o", path, got, want)
	}
}

func canonicalTempDir(t *testing.T) string {
	t.Helper()
	resolved, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	return resolved
}
