//go:build darwin || linux

package linkworkspace_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
)

const testDigest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func TestExecutorRecoversJournalProducedWithUnixWorkspace(t *testing.T) {
	source := t.TempDir()
	target := t.TempDir()
	if err := os.Mkdir(filepath.Join(source, "bin"), 0o755); err != nil {
		t.Fatalf("mkdir source bin: %v", err)
	}
	if err := os.WriteFile(filepath.Join(source, "bin", "mainframe"), nil, 0o755); err != nil {
		t.Fatalf("write source: %v", err)
	}
	workspace, err := linkworkspace.New(
		source,
		map[domain.RootID]string{domain.RootUserBin: target},
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	preview := executor.Preview{
		Release: executor.ReleaseIdentity{ID: "release", IndexSHA256: testDigest},
		Desired: []domain.ComponentID{"mainframe-cli"},
		Plan: domain.Plan{Operations: []domain.Operation{{
			ComponentID: "mainframe-cli",
			Kind:        domain.OperationInstall,
			Artifact: domain.Artifact{Location: domain.Location{
				Root: domain.RootUserBin,
				Path: "mainframe",
			}},
			SourcePath: "bin/mainframe",
		}}},
	}
	store := &memoryStore{}
	runner := executor.New(memoryLocker{}, store, staticRefresher{preview}, workspace)
	if _, err := runner.Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if _, err := runner.Recover(); err != nil {
		t.Fatalf("Recover() rejected its own journal: %v", err)
	}
}

type memoryStore struct {
	journal *executor.Journal
}

func (store *memoryStore) Load() (*executor.Journal, error) {
	return store.journal, nil
}

func (store *memoryStore) Save(journal executor.Journal) error {
	clone := journal
	clone.Desired = append([]domain.ComponentID(nil), journal.Desired...)
	clone.Steps = append([]executor.JournalMutation(nil), journal.Steps...)
	store.journal = &clone
	return nil
}

func (store *memoryStore) Cleanup() error {
	return nil
}

type memoryLocker struct{}

func (memoryLocker) Lock() (executor.Lock, error) {
	return memoryLock{}, nil
}

type memoryLock struct{}

func (memoryLock) Unlock() error {
	return nil
}

type staticRefresher struct {
	preview executor.Preview
}

func (refresher staticRefresher) Refresh([]domain.ComponentID) (executor.Preview, error) {
	return refresher.preview, nil
}
