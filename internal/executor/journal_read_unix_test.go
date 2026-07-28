//go:build unix

package executor

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadUnixJournalDoesNotCreateMissingState(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "missing", "mainframe")

	journal, err := ReadUnixJournal(root)
	if err != nil || journal != nil {
		t.Fatalf("ReadUnixJournal() = %#v, %v", journal, err)
	}
	if _, err := os.Stat(root); !os.IsNotExist(err) {
		t.Fatalf("read-only journal lookup created state: %v", err)
	}
}

func TestReadUnixJournalLoadsExistingStateWithoutMutation(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	journal := journalWith(
		TransactionInProgress,
		installJournalStep("launcher", StepPrepared),
	)
	if err := state.Save(*journal); err != nil {
		t.Fatalf("Save() error = %v", err)
	}
	if err := state.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}

	loaded, err := ReadUnixJournal(root)
	if err != nil || loaded == nil || loaded.Steps[0] != journal.Steps[0] {
		t.Fatalf("ReadUnixJournal() = %#v, %v", loaded, err)
	}
}
