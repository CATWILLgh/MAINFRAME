//go:build darwin || linux

package codexstate

import (
	"errors"
	"os"
	"os/exec"
	"syscall"

	"golang.org/x/sys/unix"
)

func configureCommand(command *exec.Cmd) {
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	command.Cancel = func() error {
		return terminateCommand(command)
	}
}

func terminateCommand(command *exec.Cmd) error {
	if command == nil || command.Process == nil {
		return nil
	}
	err := unix.Kill(-command.Process.Pid, unix.SIGKILL)
	if errors.Is(err, unix.ESRCH) {
		return os.ErrProcessDone
	}
	return err
}
