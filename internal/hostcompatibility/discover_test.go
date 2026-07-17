package hostcompatibility

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"howett.net/plist"
)

func TestDiscoverApplicationsReadsXMLAndBinaryPlists(t *testing.T) {
	root := t.TempDir()
	writeApplication(t, root, "Binary.app", "app.binary", "2.0", plist.BinaryFormat)
	writeApplication(t, root, "XML.app", "app.xml", "1.0", plist.XMLFormat)

	got := discoverApplications("darwin", []string{root}, scanLimits{MaxEntries: 20, MaxPlistBytes: 4096})
	want := ApplicationInventory{Available: true, Complete: true, Applications: []Application{
		{BundleIdentifier: "app.binary", Version: "2.0"},
		{BundleIdentifier: "app.xml", Version: "1.0"},
	}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("inventory = %#v, want %#v", got, want)
	}
}

func TestDiscoverApplicationsMarksPartialScansIncomplete(t *testing.T) {
	tests := []struct {
		name  string
		setup func(*testing.T, string)
		limit scanLimits
	}{
		{
			name: "malformed plist",
			setup: func(t *testing.T, root string) {
				writeRawPlist(t, root, "Broken.app", []byte("not a plist"))
			},
			limit: scanLimits{MaxEntries: 20, MaxPlistBytes: 4096},
		},
		{
			name: "oversized plist",
			setup: func(t *testing.T, root string) {
				writeRawPlist(t, root, "Large.app", make([]byte, 33))
			},
			limit: scanLimits{MaxEntries: 20, MaxPlistBytes: 32},
		},
		{
			name: "entry limit",
			setup: func(t *testing.T, root string) {
				writeApplication(t, root, "A.app", "app.a", "1", plist.XMLFormat)
				writeApplication(t, root, "B.app", "app.b", "1", plist.XMLFormat)
			},
			limit: scanLimits{MaxEntries: 1, MaxPlistBytes: 4096},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := t.TempDir()
			test.setup(t, root)
			got := discoverApplications("darwin", []string{root}, test.limit)
			if !got.Available || got.Complete {
				t.Fatalf("inventory = %#v, want available incomplete", got)
			}
		})
	}
}

func TestDiscoverApplicationsRejectsUnsafeMetadataAndVersionFallback(t *testing.T) {
	root := t.TempDir()
	writeApplication(t, root, "Control.app", "app.control", "2.2.1\x1b[2J", plist.XMLFormat)
	payload, err := plist.Marshal(map[string]string{
		"CFBundleIdentifier": "app.fallback",
		"CFBundleVersion":    "2.2.1",
	}, plist.XMLFormat)
	if err != nil {
		t.Fatal(err)
	}
	writeRawPlist(t, root, "Fallback.app", payload)

	got := DiscoverApplications("darwin", []string{root})
	if !got.Available || got.Complete || len(got.Applications) != 0 {
		t.Fatalf("inventory = %#v, want incomplete without applications", got)
	}
}

func TestDiscoverApplicationsAppliesAggregateBudgetsAcrossRoots(t *testing.T) {
	first := t.TempDir()
	second := t.TempDir()
	writeApplication(t, first, "First.app", "app.first", "1", plist.XMLFormat)
	writeApplication(t, second, "Second.app", "app.second", "1", plist.XMLFormat)

	got := discoverApplications("darwin", []string{first, second}, scanLimits{
		MaxEntries: 20, MaxPlistBytes: 4096, MaxTotalPlistBytes: 512,
		MaxApplications: 20,
	})
	if !got.Available || got.Complete || len(got.Applications) >= 2 {
		t.Fatalf("inventory = %#v, want bounded incomplete scan", got)
	}

	got = discoverApplications("darwin", []string{first, second}, scanLimits{
		MaxEntries: 20, MaxPlistBytes: 4096, MaxTotalPlistBytes: 8192,
		MaxApplications: 1,
	})
	if got.Complete || len(got.Applications) != 1 {
		t.Fatalf("application-limited inventory = %#v", got)
	}
}

func TestDiscoverApplicationsHandlesMissingRootsDuplicatesAndSymlinks(t *testing.T) {
	root := t.TempDir()
	writeApplication(t, root, "First.app", "app.same", "2", plist.XMLFormat)
	writeApplication(t, root, "Second.app", "app.same", "1", plist.XMLFormat)
	if err := os.Symlink(filepath.Join(root, "First.app"), filepath.Join(root, "Alias.app")); err != nil {
		t.Fatal(err)
	}

	got := DiscoverApplications("darwin", []string{filepath.Join(root, "missing"), root})
	want := []Application{
		{BundleIdentifier: "app.same", Version: "1"},
		{BundleIdentifier: "app.same", Version: "2"},
	}
	if !got.Available || !got.Complete || !reflect.DeepEqual(got.Applications, want) {
		t.Fatalf("inventory = %#v, want applications %#v", got, want)
	}
}

func TestDiscoverApplicationsDoesNoIOOutsideDarwin(t *testing.T) {
	got := DiscoverApplications("linux", []string{"\x00invalid"})
	if got.Available || got.Complete || len(got.Applications) != 0 {
		t.Fatalf("inventory = %#v, want unavailable", got)
	}
}

func writeApplication(t *testing.T, root, name, identifier, version string, format int) {
	t.Helper()
	payload, err := plist.Marshal(map[string]string{
		"CFBundleIdentifier":         identifier,
		"CFBundleShortVersionString": version,
	}, format)
	if err != nil {
		t.Fatal(err)
	}
	writeRawPlist(t, root, name, payload)
}

func writeRawPlist(t *testing.T, root, name string, payload []byte) {
	t.Helper()
	contents := filepath.Join(root, name, "Contents")
	if err := os.MkdirAll(contents, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(contents, "Info.plist"), payload, 0o644); err != nil {
		t.Fatal(err)
	}
}
