//go:build darwin || linux

package linkworkspace

import (
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/sys/unix"
)

type configurationProbeRemnantCase struct {
	name    string
	probe   string
	payload []byte
	wantErr bool
}

var configurationProbeRemnantCases = []configurationProbeRemnantCase{
	{
		name:    "empty interrupted first write",
		probe:   configurationProbeNameA,
		payload: nil,
	},
	{
		name:    "partial interrupted second write",
		probe:   configurationProbeNameB,
		payload: configurationProbePayloadB[:8],
	},
	{
		name:    "exchanged first entry",
		probe:   configurationProbeNameA,
		payload: configurationProbePayloadB,
	},
	{
		name:    "completed no-replace entry",
		probe:   configurationProbeNameC,
		payload: configurationProbePayloadA,
	},
	{
		name:    "foreign",
		probe:   configurationProbeNameA,
		payload: []byte("foreign"),
		wantErr: true,
	},
}

func TestConfigurationRenameCapabilityProbeLeavesDirectoryEmpty(t *testing.T) {
	directory := t.TempDir()
	fd, err := unix.Open(directory, directoryOpenFlags, 0)
	if err != nil {
		t.Fatalf("open probe directory: %v", err)
	}
	defer unix.Close(fd)

	if err := probeConfigurationRenames(fd); err != nil {
		t.Fatalf("probeConfigurationRenames() error = %v", err)
	}

	entries, err := os.ReadDir(directory)
	if err != nil {
		t.Fatalf("read probe directory: %v", err)
	}
	if len(entries) != 0 {
		t.Fatalf("capability probe left entries: %#v", entries)
	}
}

func TestFinalizeConfigurationPrivateCleansOnlyRecognizedProbeRemnants(t *testing.T) {
	for _, test := range configurationProbeRemnantCases {
		t.Run(test.name, func(t *testing.T) {
			fixture := newConfigurationFixture(t, "settings.json", nil, 0)
			mutation := fixture.preparedMutation(t, []byte("after"), 0o600)
			identity, err := fixture.workspace.PrepareConfigurationPrivate(mutation)
			if err != nil {
				t.Fatalf("PrepareConfigurationPrivate() error = %v", err)
			}
			mutation.Private.Identity = identity
			probe := filepath.Join(
				fixture.target,
				mutation.Private.Name,
				test.probe,
			)
			if err := os.WriteFile(probe, test.payload, 0o600); err != nil {
				t.Fatalf("write probe remnant: %v", err)
			}

			err = fixture.workspace.FinalizeConfigurationPrivate(mutation)

			if (err != nil) != test.wantErr {
				t.Fatalf("FinalizeConfigurationPrivate() error = %v", err)
			}
			_, statErr := os.Lstat(probe)
			if test.wantErr && statErr != nil {
				t.Fatal("foreign probe remnant was deleted")
			}
			if !test.wantErr && !os.IsNotExist(statErr) {
				t.Fatalf("recognized probe remnant remains: %v", statErr)
			}
		})
	}
}
