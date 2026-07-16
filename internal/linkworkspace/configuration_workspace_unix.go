//go:build darwin || linux

package linkworkspace

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"golang.org/x/sys/unix"
)

type configurationContext struct {
	parentFD  int
	privateFD int
	finalName string
	parent    executor.FileIdentity
}

func (context configurationContext) close() {
	unix.Close(context.privateFD)
	unix.Close(context.parentFD)
}

func (workspace Workspace) InspectConfiguration(
	target domain.Location,
) (executor.ConfigurationState, error) {
	parentFD, name, parent, err := workspace.openLocationParent(target)
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	defer unix.Close(parentFD)
	return inspectConfigurationAt(parentFD, name, parent)
}

func inspectConfigurationAt(
	parentFD int,
	name string,
	parent executor.FileIdentity,
) (executor.ConfigurationState, error) {
	fd, err := unix.Openat(
		parentFD,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if isMissing(err) {
		return executor.ConfigurationState{Parent: parent}, nil
	}
	if err != nil {
		return executor.ConfigurationState{}, fmt.Errorf("open configuration: %w", err)
	}
	file := os.NewFile(uintptr(fd), name)
	if file == nil {
		unix.Close(fd)
		return executor.ConfigurationState{}, errors.New("open configuration descriptor")
	}
	defer file.Close()
	before, err := configurationFileStat(fd)
	if err != nil {
		return executor.ConfigurationState{}, err
	}
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return executor.ConfigurationState{}, fmt.Errorf("hash configuration: %w", err)
	}
	after, err := configurationFileStat(fd)
	if err != nil || !sameConfigurationStat(before, after) {
		return executor.ConfigurationState{}, errors.Join(
			err,
			errors.New("configuration changed while being inspected"),
		)
	}
	named, _, err := identityAt(parentFD, name)
	if err != nil || named != identityOfStat(after) {
		return executor.ConfigurationState{}, errors.Join(
			err,
			errors.New("configuration name changed while being inspected"),
		)
	}
	return executor.ConfigurationState{
		Exists: true,
		SHA256: hex.EncodeToString(hash.Sum(nil)),
		Mode:   uint32(after.Mode) & 0o777,
		Parent: parent,
		Entry:  identityOfStat(after),
	}, nil
}

func configurationFileStat(fd int) (unix.Stat_t, error) {
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		return stat, err
	}
	if stat.Mode&unix.S_IFMT != unix.S_IFREG {
		return stat, errors.New("configuration is not a regular file")
	}
	if stat.Uid != uint32(os.Geteuid()) {
		return stat, errors.New("configuration is not owned by the current user")
	}
	if stat.Nlink != 1 {
		return stat, errors.New("configuration has external hard links")
	}
	if stat.Mode&0o400 == 0 {
		return stat, errors.New("configuration is not owner-readable")
	}
	return stat, nil
}

func (workspace Workspace) PrepareConfigurationPrivate(
	mutation executor.JournalConfigurationMutation,
) (executor.FileIdentity, error) {
	identity, err := workspace.PreparePrivate(executor.WorkspaceMutation{
		Location: mutation.Target,
		Parent:   mutation.Parent,
		Private:  mutation.Private,
	})
	parentFD, _, parent, openErr := workspace.openLocationParent(mutation.Target)
	if openErr != nil {
		return executor.FileIdentity{}, errors.Join(err, openErr)
	}
	defer unix.Close(parentFD)
	if parent != mutation.Parent {
		return executor.FileIdentity{}, errors.Join(
			err,
			errors.New("configuration parent identity changed"),
		)
	}
	return identity, errors.Join(err, syncDirectory(parentFD))
}

func (workspace Workspace) FinalizeConfigurationPrivate(
	mutation executor.JournalConfigurationMutation,
) error {
	parentFD, _, parent, err := workspace.openLocationParent(mutation.Target)
	if err != nil {
		return err
	}
	defer unix.Close(parentFD)
	if parent != mutation.Parent {
		return errors.New("configuration parent identity changed")
	}
	privateFD, _, err := openPrivateAt(
		parentFD,
		mutation.Private.Name,
		mutation.Private.Identity,
	)
	if isMissing(err) {
		return syncDirectory(parentFD)
	}
	if err != nil {
		return err
	}
	defer unix.Close(privateFD)
	if err := cleanupConfigurationProbe(privateFD); err != nil {
		return err
	}
	empty, err := directoryEmpty(privateFD)
	if err != nil || !empty {
		return errors.Join(err, errors.New("configuration private directory is not empty"))
	}
	if err := unix.Unlinkat(parentFD, mutation.Private.Name, unix.AT_REMOVEDIR); err != nil {
		return err
	}
	return syncDirectory(parentFD)
}

func (workspace Workspace) openConfigurationMutation(
	mutation executor.JournalConfigurationMutation,
) (configurationContext, error) {
	if !validFileIdentity(mutation.Parent) ||
		!validFileIdentity(mutation.Private.Identity) ||
		mutation.StagedName != "staged" {
		return configurationContext{}, errors.New("invalid configuration workspace")
	}
	parentFD, final, parent, err := workspace.openLocationParent(mutation.Target)
	if err != nil {
		return configurationContext{}, err
	}
	if parent != mutation.Parent {
		unix.Close(parentFD)
		return configurationContext{}, errors.New("configuration parent identity changed")
	}
	privateFD, _, err := openPrivateAt(
		parentFD,
		mutation.Private.Name,
		mutation.Private.Identity,
	)
	if err != nil {
		unix.Close(parentFD)
		return configurationContext{}, err
	}
	return configurationContext{
		parentFD: parentFD, privateFD: privateFD,
		finalName: final, parent: parent,
	}, nil
}

func validConfigurationImage(image executor.ConfigurationFileImage) bool {
	if !image.Exists {
		return image.SHA256 == "" && image.Mode == 0 &&
			image.Entry == (executor.FileIdentity{})
	}
	if len(image.SHA256) != sha256.Size*2 ||
		(image.Mode != 0o400 && image.Mode != 0o600) {
		return false
	}
	_, err := hex.DecodeString(image.SHA256)
	return err == nil
}

func matchesConfigurationImage(
	state executor.ConfigurationState,
	image executor.ConfigurationFileImage,
) bool {
	return state.Exists == image.Exists &&
		state.SHA256 == image.SHA256 &&
		state.Mode == image.Mode &&
		state.Entry == image.Entry
}
