//go:build darwin || linux

package executor

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
)

func TestCompatibilityUtilitySharesExecutorLock(t *testing.T) {
	root := filepath.Join(canonicalTempDir(t), "state")
	state := openTestState(t, root)
	defer state.Close()
	lock, err := state.Lock()
	if err != nil {
		t.Fatalf("Lock() error = %v", err)
	}
	lockFile, err := os.OpenFile(
		filepath.Join(root, lockFileName),
		os.O_RDWR,
		0,
	)
	if err != nil {
		t.Fatalf("open compatibility lock: %v", err)
	}
	defer lockFile.Close()

	if err := compatibilityLockCommand(lockFile).Run(); err == nil {
		t.Fatal("compatibility utility acquired the Go executor lock")
	}
	if err := lock.Unlock(); err != nil {
		t.Fatalf("Unlock() error = %v", err)
	}
	if err := compatibilityLockCommand(lockFile).Run(); err != nil {
		t.Fatalf("compatibility lock after release: %v", err)
	}
}

func compatibilityLockCommand(lockFile *os.File) *exec.Cmd {
	var command *exec.Cmd
	if runtime.GOOS == "darwin" {
		command = exec.Command("/usr/bin/lockf", "-s", "-t", "0", "3")
	} else {
		path := "/usr/bin/flock"
		if _, err := os.Stat(path); err != nil {
			path = "/bin/flock"
		}
		command = exec.Command(path, "-n", "3")
	}
	command.ExtraFiles = []*os.File{lockFile}
	return command
}
