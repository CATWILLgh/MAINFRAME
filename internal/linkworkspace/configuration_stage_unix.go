//go:build darwin || linux

package linkworkspace

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

func (workspace Workspace) StageConfiguration(
	mutation executor.JournalConfigurationMutation,
	payload []byte,
) (executor.FileIdentity, error) {
	if !validConfigurationImage(mutation.After) ||
		mutation.After.Entry != (executor.FileIdentity{}) {
		return executor.FileIdentity{}, errors.New("invalid configuration after-image")
	}
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return executor.FileIdentity{}, err
	}
	defer context.close()
	if err := cleanupInterruptedConfigurationStage(
		context.privateFD,
		mutation,
	); err != nil {
		return executor.FileIdentity{}, err
	}
	state, err := inspectPrivateConfiguration(
		context.privateFD,
		mutation.StagedName,
		context.parent,
	)
	if err == nil && state.Exists {
		if !matchesStagedConfiguration(state, mutation) {
			return executor.FileIdentity{}, errors.New("staged configuration differs")
		}
		return state.Entry, errors.Join(
			syncConfigurationAt(context.privateFD, mutation.StagedName),
			syncDirectory(context.privateFD),
		)
	}
	if err != nil && !isMissing(err) {
		return executor.FileIdentity{}, err
	}
	if err := createStagedConfiguration(context.privateFD, mutation, payload); err != nil {
		return executor.FileIdentity{}, err
	}
	if err := syncDirectory(context.privateFD); err != nil {
		return executor.FileIdentity{}, err
	}
	state, err = inspectPrivateConfiguration(
		context.privateFD,
		mutation.StagedName,
		context.parent,
	)
	if err != nil || !matchesStagedConfiguration(state, mutation) {
		return executor.FileIdentity{}, errors.Join(
			err,
			errors.New("staged configuration verification failed"),
		)
	}
	return state.Entry, nil
}

func (workspace Workspace) AdoptStagedConfiguration(
	mutation executor.JournalConfigurationMutation,
) (executor.FileIdentity, bool, error) {
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return executor.FileIdentity{}, false, err
	}
	defer context.close()
	if err := cleanupInterruptedConfigurationStage(
		context.privateFD,
		mutation,
	); err != nil {
		return executor.FileIdentity{}, false, err
	}
	state, err := inspectPrivateConfiguration(
		context.privateFD,
		mutation.StagedName,
		context.parent,
	)
	if err != nil {
		return executor.FileIdentity{}, false, err
	}
	if !state.Exists {
		return executor.FileIdentity{}, false, nil
	}
	if !matchesStagedConfiguration(state, mutation) {
		return executor.FileIdentity{}, false, errors.New(
			"staged configuration differs",
		)
	}
	return state.Entry, true, nil
}

func createStagedConfiguration(
	privateFD int,
	mutation executor.JournalConfigurationMutation,
	payload []byte,
) error {
	if configurationDigest(payload) != mutation.After.SHA256 {
		return errors.New("configuration payload digest differs")
	}
	fd, err := unix.Openat(
		privateFD,
		configurationWritingName,
		unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0o600,
	)
	if err != nil {
		return fmt.Errorf("create staged configuration: %w", err)
	}
	file := os.NewFile(uintptr(fd), configurationWritingName)
	if file == nil {
		unix.Close(fd)
		return errors.New("open staged configuration descriptor")
	}
	writeErr := populateStagedConfiguration(file, mutation, payload)
	closeErr := file.Close()
	if writeErr != nil || closeErr != nil {
		return errors.Join(writeErr, closeErr)
	}
	if err := renameNoReplace(
		privateFD,
		configurationWritingName,
		privateFD,
		mutation.StagedName,
	); err != nil {
		return fmt.Errorf("publish staged configuration: %w", err)
	}
	return nil
}

func populateStagedConfiguration(
	file *os.File,
	mutation executor.JournalConfigurationMutation,
	payload []byte,
) error {
	if err := file.Chmod(0o600); err != nil {
		return fmt.Errorf("set writing configuration mode: %w", err)
	}
	if err := writeAll(file, payload); err != nil {
		return err
	}
	if err := file.Chmod(os.FileMode(mutation.After.Mode)); err != nil {
		return fmt.Errorf("set staged configuration mode: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync staged configuration: %w", err)
	}
	return nil
}

func writeAll(file *os.File, payload []byte) error {
	for len(payload) > 0 {
		written, err := file.Write(payload)
		if err != nil {
			return fmt.Errorf("write staged configuration: %w", err)
		}
		if written == 0 {
			return errors.New("write staged configuration made no progress")
		}
		payload = payload[written:]
	}
	return nil
}

func inspectPrivateConfiguration(
	privateFD int,
	name string,
	parent executor.FileIdentity,
) (executor.ConfigurationState, error) {
	state, err := inspectConfigurationAt(privateFD, name, parent)
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	return state, nil
}

func matchesStagedConfiguration(
	state executor.ConfigurationState,
	mutation executor.JournalConfigurationMutation,
) bool {
	if !state.Exists ||
		state.SHA256 != mutation.After.SHA256 ||
		state.Mode != mutation.After.Mode {
		return false
	}
	return mutation.StagedIdentity == (executor.FileIdentity{}) ||
		state.Entry == mutation.StagedIdentity
}

func configurationDigest(payload []byte) string {
	sum := sha256.Sum256(payload)
	return fmt.Sprintf("%x", sum)
}

func syncConfigurationAt(parentFD int, name string) error {
	fd, err := unix.Openat(
		parentFD,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if err != nil {
		return err
	}
	defer unix.Close(fd)
	return unix.Fsync(fd)
}
