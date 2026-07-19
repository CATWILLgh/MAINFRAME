//go:build darwin || linux

package codexstate

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"golang.org/x/sys/unix"
)

func TestAppServerClientKillsDescendantsOnInspectionCancellation(t *testing.T) {
	binary := filepath.Join(t.TempDir(), "codex")
	fifo := binary + ".fifo"
	if err := unix.Mkfifo(fifo, 0o600); err != nil {
		t.Fatalf("create descendant lifetime pipe: %v", err)
	}
	reader, err := unix.Open(fifo, unix.O_RDONLY|unix.O_NONBLOCK|unix.O_CLOEXEC, 0)
	if err != nil {
		t.Fatalf("open descendant lifetime pipe: %v", err)
	}
	defer unix.Close(reader)
	script := "#!/bin/sh\nexec 3>\"$0.fifo\"\nsleep 10 &\necho ready > \"$0.ready\"\nwait\n"
	if err := os.WriteFile(binary, []byte(script), 0o700); err != nil {
		t.Fatalf("write fake Codex: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	completed := make(chan error, 1)
	go func() {
		_, err := (AppServerClient{Binary: binary}).ListHooks(ctx, "/workspace")
		completed <- err
	}()
	waitForPath(t, binary+".ready", 2*time.Second)
	if !pipeHasWriter(reader) {
		t.Fatal("descendant did not inherit the lifetime pipe")
	}
	started := time.Now()
	cancel()
	err = <-completed
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("ListHooks() error = %v", err)
	}
	if elapsed := time.Since(started); elapsed > time.Second {
		t.Fatalf("cancellation took %s", elapsed)
	}
	if !waitForPipeEOF(reader, time.Second) {
		t.Fatal("descendant lifetime pipe remained open after cancellation")
	}
}

func waitForPath(t *testing.T, path string, limit time.Duration) {
	t.Helper()
	deadline := time.Now().Add(limit)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); err == nil {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("path %q was not published", path)
}

func pipeHasWriter(descriptor int) bool {
	buffer := make([]byte, 1)
	_, err := unix.Read(descriptor, buffer)
	return errors.Is(err, unix.EAGAIN) || errors.Is(err, unix.EWOULDBLOCK)
}

func waitForPipeEOF(descriptor int, limit time.Duration) bool {
	deadline := time.Now().Add(limit)
	for time.Now().Before(deadline) {
		count, err := unix.Read(descriptor, make([]byte, 1))
		if count == 0 && err == nil {
			return true
		}
		time.Sleep(10 * time.Millisecond)
	}
	count, err := unix.Read(descriptor, make([]byte, 1))
	return count == 0 && err == nil
}
