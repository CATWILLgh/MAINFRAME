//go:build !darwin && !linux

package codexstate

import "os/exec"

func configureCommand(_ *exec.Cmd) {}

func terminateCommand(command *exec.Cmd) error {
	if command == nil || command.Process == nil {
		return nil
	}
	return command.Process.Kill()
}
