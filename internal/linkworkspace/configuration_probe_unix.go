//go:build darwin || linux

package linkworkspace

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"

	"golang.org/x/sys/unix"
)

const (
	configurationProbeNameA = ".capability-a"
	configurationProbeNameB = ".capability-b"
	configurationProbeNameC = ".capability-c"
)

var (
	configurationProbePayloadA = []byte("mainframe-capability-a\n")
	configurationProbePayloadB = []byte("mainframe-capability-b\n")
)

func probeConfigurationRenames(directory int) (result error) {
	if err := cleanupConfigurationProbe(directory); err != nil {
		return err
	}
	defer func() {
		result = errors.Join(result, cleanupConfigurationProbe(directory))
	}()
	if err := createConfigurationProbe(
		directory,
		configurationProbeNameA,
		configurationProbePayloadA,
	); err != nil {
		return err
	}
	if err := createConfigurationProbe(
		directory,
		configurationProbeNameB,
		configurationProbePayloadB,
	); err != nil {
		return err
	}
	if err := syncDirectory(directory); err != nil {
		return err
	}
	if err := probeConfigurationExchange(directory); err != nil {
		return err
	}
	return probeConfigurationNoReplace(directory)
}

func probeConfigurationExchange(directory int) error {
	if err := renameExchange(
		directory,
		configurationProbeNameA,
		directory,
		configurationProbeNameB,
	); err != nil {
		return fmt.Errorf("probe configuration exchange: %w", err)
	}
	if err := syncDirectory(directory); err != nil {
		return err
	}
	if err := requireConfigurationProbe(
		directory,
		configurationProbeNameA,
		configurationProbePayloadB,
	); err != nil {
		return err
	}
	if err := requireConfigurationProbe(
		directory,
		configurationProbeNameB,
		configurationProbePayloadA,
	); err != nil {
		return err
	}
	return nil
}

func probeConfigurationNoReplace(directory int) error {
	if err := renameNoReplace(
		directory,
		configurationProbeNameB,
		directory,
		configurationProbeNameC,
	); err != nil {
		return fmt.Errorf("probe configuration no-replace rename: %w", err)
	}
	if err := syncDirectory(directory); err != nil {
		return err
	}
	return requireConfigurationProbe(
		directory,
		configurationProbeNameC,
		configurationProbePayloadA,
	)
}

func createConfigurationProbe(
	directory int,
	name string,
	payload []byte,
) error {
	fd, err := unix.Openat(
		directory,
		name,
		unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC,
		0o600,
	)
	if err != nil {
		return fmt.Errorf("create configuration capability probe: %w", err)
	}
	file := os.NewFile(uintptr(fd), name)
	if file == nil {
		unix.Close(fd)
		return errors.New("open configuration capability probe")
	}
	defer file.Close()
	if err := file.Chmod(0o600); err != nil {
		return fmt.Errorf("set configuration capability probe mode: %w", err)
	}
	if err := writeAll(file, payload); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync configuration capability probe: %w", err)
	}
	return nil
}

func requireConfigurationProbe(
	directory int,
	name string,
	expected []byte,
) error {
	payload, exists, err := readConfigurationProbe(directory, name)
	if err != nil {
		return err
	}
	if !exists || !bytes.Equal(payload, expected) {
		return fmt.Errorf("configuration capability probe %q changed", name)
	}
	return nil
}

func cleanupConfigurationProbe(directory int) error {
	names := []string{
		configurationProbeNameA,
		configurationProbeNameB,
		configurationProbeNameC,
	}
	existing := make([]string, 0, len(names))
	for _, name := range names {
		payload, exists, err := readConfigurationProbe(directory, name)
		if err != nil {
			return err
		}
		if !exists {
			continue
		}
		if !validConfigurationProbeRemnant(name, payload) {
			return fmt.Errorf("configuration capability probe %q differs", name)
		}
		existing = append(existing, name)
	}
	for _, name := range existing {
		if err := unix.Unlinkat(directory, name, 0); err != nil {
			return fmt.Errorf("remove configuration capability probe: %w", err)
		}
	}
	if len(existing) == 0 {
		return nil
	}
	return syncDirectory(directory)
}

func validConfigurationProbeRemnant(name string, payload []byte) bool {
	switch name {
	case configurationProbeNameA:
		return bytes.HasPrefix(configurationProbePayloadA, payload) ||
			bytes.Equal(configurationProbePayloadB, payload)
	case configurationProbeNameB:
		return bytes.HasPrefix(configurationProbePayloadB, payload) ||
			bytes.Equal(configurationProbePayloadA, payload)
	case configurationProbeNameC:
		return bytes.Equal(configurationProbePayloadA, payload)
	default:
		return false
	}
}

func readConfigurationProbe(
	directory int,
	name string,
) ([]byte, bool, error) {
	file, fd, exists, err := openConfigurationProbe(directory, name)
	if err != nil || !exists {
		return nil, exists, err
	}
	defer file.Close()
	before, err := configurationFileStat(fd)
	if err != nil || before.Mode&0o777 != 0o600 {
		return nil, false, errors.Join(
			err,
			errors.New("configuration capability probe metadata differs"),
		)
	}
	payload, err := readConfigurationProbePayload(file)
	if err != nil {
		return nil, false, err
	}
	if err := verifyConfigurationProbe(directory, name, fd, before); err != nil {
		return nil, false, err
	}
	return payload, true, nil
}

func openConfigurationProbe(
	directory int,
	name string,
) (*os.File, int, bool, error) {
	fd, err := unix.Openat(
		directory,
		name,
		unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC,
		0,
	)
	if isMissing(err) {
		return nil, 0, false, nil
	}
	if err != nil {
		return nil, 0, false, err
	}
	file := os.NewFile(uintptr(fd), name)
	if file == nil {
		unix.Close(fd)
		return nil, 0, false, errors.New("open configuration capability probe")
	}
	return file, fd, true, nil
}

func readConfigurationProbePayload(file *os.File) ([]byte, error) {
	limit := int64(len(configurationProbePayloadA) + 1)
	payload, err := io.ReadAll(io.LimitReader(file, limit))
	if err != nil || int64(len(payload)) == limit {
		return nil, errors.Join(
			err,
			errors.New("configuration capability probe size differs"),
		)
	}
	return payload, nil
}

func verifyConfigurationProbe(
	directory int,
	name string,
	fd int,
	before unix.Stat_t,
) error {
	after, err := configurationFileStat(fd)
	if err != nil || !sameConfigurationStat(before, after) {
		return errors.Join(
			err,
			errors.New("configuration capability probe changed"),
		)
	}
	named, _, err := identityAt(directory, name)
	if err != nil || named != identityOfStat(after) {
		return errors.Join(
			err,
			errors.New("configuration capability probe name changed"),
		)
	}
	return nil
}
