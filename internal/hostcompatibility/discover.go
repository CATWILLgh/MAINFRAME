package hostcompatibility

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"howett.net/plist"
)

const (
	defaultMaxEntries     = 4096
	defaultMaxPlistBytes  = 1 << 20
	defaultMaxTotalBytes  = 16 << 20
	defaultMaxApps        = 256
	readDirectoryBatch    = 128
	maxBundleIdentifier   = 255
	maxApplicationVersion = 64
)

type scanLimits struct {
	MaxEntries         int
	MaxPlistBytes      int64
	MaxTotalPlistBytes int64
	MaxApplications    int
}

type scanBudget struct {
	entries      int
	plistBytes   int64
	applications int
}

type applicationPlist struct {
	BundleIdentifier string `plist:"CFBundleIdentifier"`
	ShortVersion     string `plist:"CFBundleShortVersionString"`
}

func DiscoverApplications(goos string, roots []string) ApplicationInventory {
	return discoverApplications(goos, roots, scanLimits{
		MaxEntries: defaultMaxEntries, MaxPlistBytes: defaultMaxPlistBytes,
		MaxTotalPlistBytes: defaultMaxTotalBytes, MaxApplications: defaultMaxApps,
	})
}

func discoverApplications(
	goos string,
	paths []string,
	limits scanLimits,
) ApplicationInventory {
	if goos != "darwin" {
		return ApplicationInventory{}
	}
	limits = normalizedLimits(limits)
	inventory := ApplicationInventory{Available: true, Complete: true}
	budget := &scanBudget{}
	for _, path := range paths {
		applications, complete := scanRoot(path, limits, budget)
		inventory.Applications = append(inventory.Applications, applications...)
		inventory.Complete = inventory.Complete && complete
	}
	slices.SortFunc(inventory.Applications, compareApplications)
	inventory.Applications = slices.Compact(inventory.Applications)
	return inventory
}

func normalizedLimits(limits scanLimits) scanLimits {
	if limits.MaxTotalPlistBytes <= 0 {
		limits.MaxTotalPlistBytes = defaultMaxTotalBytes
	}
	if limits.MaxApplications <= 0 {
		limits.MaxApplications = defaultMaxApps
	}
	return limits
}

func scanRoot(path string, limits scanLimits, budget *scanBudget) ([]Application, bool) {
	root, err := os.OpenRoot(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, true
	}
	if err != nil {
		return nil, false
	}
	defer root.Close()

	directory, err := root.Open(".")
	if err != nil {
		return nil, false
	}
	defer directory.Close()
	return scanDirectory(root, directory, limits, budget)
}

func scanDirectory(
	root *os.Root,
	directory *os.File,
	limits scanLimits,
	budget *scanBudget,
) ([]Application, bool) {
	applications := make([]Application, 0)
	complete := true
	for {
		entries, err := directory.ReadDir(readDirectoryBatch)
		if err != nil && !errors.Is(err, io.EOF) {
			return applications, false
		}
		for _, entry := range entries {
			budget.entries++
			if budget.entries > limits.MaxEntries {
				return applications, false
			}
			if !strings.HasSuffix(entry.Name(), ".app") || entry.Type()&os.ModeSymlink != 0 {
				continue
			}
			remaining := limits.MaxTotalPlistBytes - budget.plistBytes
			application, bytesRead, valid := readApplication(
				root, entry.Name(), limits.MaxPlistBytes, remaining,
			)
			budget.plistBytes += bytesRead
			if valid {
				if budget.applications >= limits.MaxApplications {
					return applications, false
				}
				applications = append(applications, application)
				budget.applications++
			} else {
				complete = false
			}
		}
		if errors.Is(err, io.EOF) {
			return applications, complete
		}
	}
}

func readApplication(
	root *os.Root,
	name string,
	maxBytes int64,
	remainingBytes int64,
) (Application, int64, bool) {
	path := filepath.Join(name, "Contents", "Info.plist")
	info, err := root.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Size() > maxBytes ||
		info.Size() > remainingBytes {
		return Application{}, 0, false
	}
	file, err := root.Open(path)
	if err != nil {
		return Application{}, 0, false
	}
	defer file.Close()
	readLimit := min(maxBytes, remainingBytes)
	payload, err := io.ReadAll(io.LimitReader(file, readLimit+1))
	if err != nil || int64(len(payload)) > readLimit {
		return Application{}, int64(len(payload)), false
	}

	var metadata applicationPlist
	if _, err := plist.Unmarshal(payload, &metadata); err != nil {
		return Application{}, int64(len(payload)), false
	}
	if !validBundleIdentifier(metadata.BundleIdentifier) ||
		!validVersion(metadata.ShortVersion) {
		return Application{}, int64(len(payload)), false
	}
	return Application{
		BundleIdentifier: metadata.BundleIdentifier,
		Version:          metadata.ShortVersion,
	}, int64(len(payload)), true
}

func validBundleIdentifier(value string) bool {
	if value == "" || len(value) > maxBundleIdentifier {
		return false
	}
	for _, character := range value {
		if character != '.' && character != '-' &&
			(character < '0' || character > '9') &&
			(character < 'A' || character > 'Z') &&
			(character < 'a' || character > 'z') {
			return false
		}
	}
	return true
}

func validVersion(value string) bool {
	if value == "" || len(value) > maxApplicationVersion {
		return false
	}
	for _, character := range value {
		if character < 0x20 || character > 0x7e {
			return false
		}
	}
	return true
}

func compareApplications(left, right Application) int {
	if result := strings.Compare(left.BundleIdentifier, right.BundleIdentifier); result != 0 {
		return result
	}
	return strings.Compare(left.Version, right.Version)
}
