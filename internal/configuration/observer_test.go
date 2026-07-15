package configuration_test

import (
	"errors"
	"io/fs"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestObserveClassifiesSupportedStrategiesWithoutReadingSeedContent(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		location("index"):  {Kind: hostfs.EntryRegular, Content: []byte("must not be exposed")},
		location("config"): {Kind: hostfs.EntryDirectory},
		location("shell"):  {Kind: hostfs.EntryRegular, Content: []byte("other\nsource env\n")},
	}}
	resources := []releasecontract.Resource{
		resource("index", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
		resource("config", releasecontract.StrategyEnsureDir, releasecontract.SupportSupported),
		withLine(resource("shell", releasecontract.StrategyShellLine, releasecontract.SupportSupported), "source env"),
		withLine(resource("optional", releasecontract.StrategyShellLineIfPresent, releasecontract.SupportSupported), "source env"),
		resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportUnimplemented),
	}

	observed, err := configuration.Observe(resources, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := []configuration.Observation{
		observation("index", configuration.Ready, configuration.ResourceExists),
		observation("config", configuration.Ready, configuration.DirectoryExists),
		observation("shell", configuration.Ready, configuration.LinePresent),
		observation("optional", configuration.NotApplicable, configuration.OptionalTargetMissing),
		observation("json", configuration.NotAssessed, configuration.ObservationUnsupported),
	}
	if !reflect.DeepEqual(observed, want) {
		t.Fatalf("observed = %#v, want %#v", observed, want)
	}
	if host.readContent[location("index")] {
		t.Fatal("seed content was read")
	}
	if !host.readContent[location("shell")] {
		t.Fatal("shell content was not read")
	}
	if _, inspected := host.readContent[location("json")]; inspected {
		t.Fatal("unsupported JSON resource was inspected")
	}
}

func TestObserveClassifiesMissingAndDriftedResources(t *testing.T) {
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		location("shell"): {Kind: hostfs.EntryRegular, Content: []byte("other\n")},
		location("link"):  {Kind: hostfs.EntrySymlink},
		location("wrong"): {Kind: hostfs.EntryDirectory},
	}, failures: map[domain.Location]error{
		location("unreadable"): errors.New("permission denied"),
	}}
	resources := []releasecontract.Resource{
		resource("seed", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
		resource("directory", releasecontract.StrategyEnsureDir, releasecontract.SupportSupported),
		withLine(resource("shell", releasecontract.StrategyShellLine, releasecontract.SupportSupported), "source env"),
		resource("link", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
		withLine(resource("wrong", releasecontract.StrategyShellLine, releasecontract.SupportSupported), "source env"),
		resource("unreadable", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
	}

	observed, err := configuration.Observe(resources, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := []configuration.Observation{
		observation("seed", configuration.NeedsChange, configuration.ResourceMissing),
		observation("directory", configuration.NeedsChange, configuration.DirectoryMissing),
		observation("shell", configuration.NeedsChange, configuration.LineMissing),
		observation("link", configuration.Attention, configuration.SymbolicLink),
		observation("wrong", configuration.Attention, configuration.WrongKind),
		observation("unreadable", configuration.Attention, configuration.InspectionFailed),
	}
	if !reflect.DeepEqual(observed, want) {
		t.Fatalf("observed = %#v, want %#v", observed, want)
	}
}

func TestObserveRejectsInvalidResourceSets(t *testing.T) {
	tests := map[string][]releasecontract.Resource{
		"duplicate": {
			resource("same", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
			resource("same", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
		},
		"unsupported strategy marked supported": {
			resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		},
		"supported shell missing desired line": {
			resource("shell", releasecontract.StrategyShellLine, releasecontract.SupportSupported),
		},
	}
	for name, resources := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := configuration.Observe(resources, &fakeHost{}); err == nil {
				t.Fatal("Observe() accepted invalid resources")
			}
		})
	}
}

type fakeHost struct {
	entries     map[domain.Location]hostfs.Entry
	failures    map[domain.Location]error
	readContent map[domain.Location]bool
}

func (host *fakeHost) Inspect(location domain.Location, includeContent bool) (hostfs.Entry, error) {
	if host.readContent == nil {
		host.readContent = make(map[domain.Location]bool)
	}
	host.readContent[location] = includeContent
	if err := host.failures[location]; err != nil {
		return hostfs.Entry{}, err
	}
	entry, exists := host.entries[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	if !includeContent {
		entry.Content = nil
	}
	return entry, nil
}

func resource(id string, strategy releasecontract.ResourceStrategy, support releasecontract.SupportStatus) releasecontract.Resource {
	return releasecontract.Resource{
		ID: id, ComponentID: "credential-tools", Strategy: strategy,
		Target: location(domain.ArtifactPath(id)), Observation: support, Apply: releasecontract.SupportUnimplemented,
	}
}

func withLine(resource releasecontract.Resource, line string) releasecontract.Resource {
	resource.DesiredLine = line
	return resource
}

func location(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootHome, Path: path}
}

func observation(id string, status configuration.Status, reason configuration.Reason) configuration.Observation {
	return configuration.Observation{
		ResourceID: id, ComponentID: "credential-tools",
		Status: status, Reason: reason,
	}
}
