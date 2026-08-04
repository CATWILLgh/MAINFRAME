package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestZCodeHookCommandProxiesStreamsAndExitCode(t *testing.T) {
	home := t.TempDir()
	script := filepath.Join(home, "mainframe", "gates", "mainframe_hook.py")
	if err := os.MkdirAll(filepath.Dir(script), 0o755); err != nil {
		t.Fatal(err)
	}
	content := []byte("import sys\ndata = sys.stdin.read()\nprint(data, end='')\nsys.exit(2)\n")
	if err := os.WriteFile(script, content, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("ZCODE_STORAGE_DIR", home)
	var output bytes.Buffer
	var errors bytes.Buffer
	code := runZCodeHookCommand(
		[]string{"PreToolUse"},
		bytes.NewBufferString(`{"toolName":"Bash"}`),
		&output,
		&errors,
	)
	if code != 2 {
		t.Fatalf("exit code = %d, want 2; stderr=%s", code, errors.String())
	}
	if output.String() != `{"toolName":"Bash"}` {
		t.Fatalf("stdout = %q", output.String())
	}
}

func TestZCodeHookCommandRejectsUnknownEventWithoutLaunching(t *testing.T) {
	t.Setenv("ZCODE_STORAGE_DIR", t.TempDir())
	var errors bytes.Buffer
	code := runZCodeHookCommand(
		[]string{"Unknown"}, bytes.NewReader(nil), &bytes.Buffer{}, &errors,
	)
	if code != 0 || errors.String() == "" {
		t.Fatalf("code=%d stderr=%q", code, errors.String())
	}
}

func TestZCodeHookCommandFailsOpenWhenBridgeIsMissing(t *testing.T) {
	t.Setenv("ZCODE_STORAGE_DIR", t.TempDir())
	var errors bytes.Buffer
	code := runZCodeHookCommand(
		[]string{"Stop"}, bytes.NewReader(nil), &bytes.Buffer{}, &errors,
	)
	if code != 0 || errors.String() == "" {
		t.Fatalf("code=%d stderr=%q", code, errors.String())
	}
}
