//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
)

func (workspace Workspace) CheckDirectoryMode(mode uint32) error {
	if mode == 0 || mode&^0o777 != 0 {
		return errors.New("invalid managed directory mode")
	}
	command := exec.Command("/bin/sh", "-c", "umask")
	command.Env = []string{"LC_ALL=C"}
	output, err := command.Output()
	if err != nil {
		return fmt.Errorf("read process umask: %w", err)
	}
	mask, err := parseProcessUmask(output)
	if err != nil {
		return err
	}
	if mask&mode != 0 {
		return fmt.Errorf(
			"process umask %#o removes required managed directory permissions %#o",
			mask,
			mode,
		)
	}
	return nil
}

func parseProcessUmask(output []byte) (uint32, error) {
	mask, err := strconv.ParseUint(strings.TrimSpace(string(output)), 8, 32)
	if err != nil || mask > 0o777 {
		return 0, errors.New("process umask has an invalid value")
	}
	return uint32(mask), nil
}
