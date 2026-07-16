//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

const (
	configurationWritingName   = ".writing"
	configurationDiscardedName = ".discarded"
)

func cleanupInterruptedConfigurationStage(
	privateFD int,
	mutation executor.JournalConfigurationMutation,
) error {
	if err := removeDiscardedConfigurationStage(privateFD, mutation); err != nil {
		return err
	}
	identity, exists, err := inspectDisposableConfigurationStage(
		privateFD,
		configurationWritingName,
		mutation.After.Mode,
	)
	if err != nil || !exists {
		return err
	}
	if err := renameNoReplace(
		privateFD,
		configurationWritingName,
		privateFD,
		configurationDiscardedName,
	); err != nil {
		return fmt.Errorf("retain interrupted configuration stage: %w", err)
	}
	if err := syncDirectory(privateFD); err != nil {
		return err
	}
	return removeExactConfigurationStage(privateFD, identity)
}

func removeDiscardedConfigurationStage(
	privateFD int,
	mutation executor.JournalConfigurationMutation,
) error {
	identity, exists, err := inspectDisposableConfigurationStage(
		privateFD,
		configurationDiscardedName,
		mutation.After.Mode,
	)
	if err != nil || !exists {
		return err
	}
	return removeExactConfigurationStage(privateFD, identity)
}

func removeExactConfigurationStage(
	privateFD int,
	expected executor.FileIdentity,
) error {
	actual, _, err := identityAt(privateFD, configurationDiscardedName)
	if err != nil || actual != expected {
		return errors.Join(
			err,
			errors.New("interrupted configuration stage identity changed"),
		)
	}
	if err := unix.Unlinkat(privateFD, configurationDiscardedName, 0); err != nil {
		return fmt.Errorf("remove interrupted configuration stage: %w", err)
	}
	return syncDirectory(privateFD)
}

func inspectDisposableConfigurationStage(
	privateFD int,
	name string,
	desiredMode uint32,
) (executor.FileIdentity, bool, error) {
	fd, err := unix.Openat(
		privateFD,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if isMissing(err) {
		return executor.FileIdentity{}, false, nil
	}
	if err != nil {
		return executor.FileIdentity{}, false, err
	}
	file := os.NewFile(uintptr(fd), name)
	if file == nil {
		unix.Close(fd)
		return executor.FileIdentity{}, false, errors.New(
			"open interrupted configuration stage",
		)
	}
	defer file.Close()
	stat, err := configurationFileStat(fd)
	if err != nil || !disposableConfigurationMode(uint32(stat.Mode)&0o777, desiredMode) {
		return executor.FileIdentity{}, false, errors.Join(
			err,
			errors.New("interrupted configuration stage metadata differs"),
		)
	}
	identity := identityOfStat(stat)
	named, _, err := identityAt(privateFD, name)
	if err != nil || named != identity {
		return executor.FileIdentity{}, false, errors.Join(
			err,
			errors.New("interrupted configuration stage name changed"),
		)
	}
	return identity, true, nil
}

func disposableConfigurationMode(actual uint32, desired uint32) bool {
	return actual == 0o600 || actual == desired
}
