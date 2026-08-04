package main

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
)

var zcodeHookEvents = map[string]bool{
	"SessionStart":       true,
	"UserPromptSubmit":   true,
	"PreToolUse":         true,
	"PermissionRequest":  true,
	"PostToolUse":        true,
	"PostToolUseFailure": true,
	"Stop":               true,
}

func runZCodeHookCommand(
	args []string,
	input io.Reader,
	output, errorOutput io.Writer,
) int {
	if len(args) != 1 || !zcodeHookEvents[args[0]] {
		fmt.Fprintln(errorOutput, "MAINFRAME ZCode hook launcher: unsupported event")
		return 0
	}
	root, err := zcodeStorageRoot()
	if err != nil {
		fmt.Fprintf(errorOutput, "MAINFRAME ZCode hook launcher degraded: %v\n", err)
		return 0
	}
	script := filepath.Join(root, "mainframe", "gates", "mainframe_hook.py")
	info, err := os.Stat(script)
	if err != nil || !info.Mode().IsRegular() {
		fmt.Fprintln(errorOutput, "MAINFRAME ZCode hook launcher degraded: bridge is unavailable")
		return 0
	}
	command := exec.Command("python3", script, args[0])
	command.Stdin = input
	command.Stdout = output
	command.Stderr = errorOutput
	if err := command.Run(); err != nil {
		if exited, ok := err.(*exec.ExitError); ok {
			if exited.ExitCode() == 2 {
				return 2
			}
			return 0
		}
		fmt.Fprintf(errorOutput, "MAINFRAME ZCode hook launcher degraded: %v\n", err)
		return 0
	}
	return 0
}

func zcodeStorageRoot() (string, error) {
	if root := os.Getenv("ZCODE_STORAGE_DIR"); root != "" {
		return filepath.Clean(root), nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve home directory: %w", err)
	}
	return filepath.Join(home, ".zcode"), nil
}
