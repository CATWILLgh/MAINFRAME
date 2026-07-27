package configuration_test

import (
	"errors"
	"fmt"
	"io/fs"
	"reflect"
	"strings"
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

func TestObserveComparesOwnedJSONFieldsFromOneTargetSnapshot(t *testing.T) {
	target := location("settings.json")
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		target: {
			Kind: hostfs.EntryRegular,
			Content: []byte(
				`{"theme":"user-owned","permissions":{"allow":["Read"],"deny":["Write"]}}`,
			),
		},
	}}
	allow := withJSON(
		resource("allow", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		target,
		releasecontract.JSONField{Pointer: "/permissions/allow", Desired: `["Read"]`},
	)
	deny := withJSON(
		resource("deny", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		target,
		releasecontract.JSONField{Pointer: "/permissions/deny", Desired: `["Other"]`},
	)

	observed, err := configuration.Observe([]releasecontract.Resource{allow, deny}, host)
	if err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
	want := []configuration.Observation{
		observation("allow", configuration.Ready, configuration.JSONFieldsMatch),
		observation("deny", configuration.NeedsChange, configuration.JSONFieldsDrifted),
	}
	if !reflect.DeepEqual(observed, want) {
		t.Fatalf("observed = %#v, want %#v", observed, want)
	}
	if host.calls[target] != 1 || !host.readContent[target] {
		t.Fatalf("JSON target inspections = %d, read content = %t", host.calls[target], host.readContent[target])
	}
}

func TestObserveClassifiesInvalidAndMissingOwnedJSON(t *testing.T) {
	tests := map[string]struct {
		content []byte
		field   releasecontract.JSONField
		status  configuration.Status
		reason  configuration.Reason
	}{
		"missing field": {
			content: []byte(`{"permissions":{}}`),
			field:   releasecontract.JSONField{Pointer: "/permissions/allow", Desired: `[]`},
			status:  configuration.NeedsChange,
			reason:  configuration.JSONFieldsDrifted,
		},
		"incompatible traversal": {
			content: []byte(`{"permissions":[]}`),
			field:   releasecontract.JSONField{Pointer: "/permissions/allow", Desired: `[]`},
			status:  configuration.Attention,
			reason:  configuration.JSONDocumentInvalid,
		},
		"duplicate key": {
			content: []byte(`{"permissions":{},"permissions":{}}`),
			field:   releasecontract.JSONField{Pointer: "/permissions/allow", Desired: `[]`},
			status:  configuration.Attention,
			reason:  configuration.JSONDocumentInvalid,
		},
		"invalid Unicode": {
			content: []byte(`{"permissions":"\uD800"}`),
			field:   releasecontract.JSONField{Pointer: "/permissions", Desired: `{}`},
			status:  configuration.Attention,
			reason:  configuration.JSONDocumentInvalid,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			target := location("settings.json")
			host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
				target: {Kind: hostfs.EntryRegular, Content: test.content},
			}}
			jsonResource := withJSON(
				resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				target,
				test.field,
			)
			observed, err := configuration.Observe([]releasecontract.Resource{jsonResource}, host)
			if err != nil {
				t.Fatalf("Observe() error = %v", err)
			}
			want := observation("json", test.status, test.reason)
			if !reflect.DeepEqual(observed[0], want) {
				t.Fatalf("observation = %#v, want %#v", observed[0], want)
			}
		})
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
		"supported JSON missing fields": {
			resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		},
		"overlapping JSON resources": {
			withJSON(
				resource("json-a", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				location("settings.json"),
				releasecontract.JSONField{Pointer: "/permissions", Desired: `{}`},
			),
			withJSON(
				resource("json-b", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				location("settings.json"),
				releasecontract.JSONField{Pointer: "/permissions/allow", Desired: `[]`},
			),
		},
		"JSON and seed share target": {
			withJSON(
				resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				location("settings.json"),
				releasecontract.JSONField{Pointer: "/permissions", Desired: `{}`},
			),
			resource("settings.json", releasecontract.StrategySeedIfAbsent, releasecontract.SupportSupported),
		},
		"JSON targets are ancestors": {
			withJSON(
				resource("json-a", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				location("settings.json"),
				releasecontract.JSONField{Pointer: "/permissions", Desired: `{}`},
			),
			withJSON(
				resource("json-b", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
				location("settings.json/child"),
				releasecontract.JSONField{Pointer: "/other", Desired: `{}`},
			),
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

func TestObserveBoundsOwnedJSONPointers(t *testing.T) {
	fields := ownedFields(0, releasecontract.MaxOwnedJSONPointers+1)
	resource := withJSON(
		resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		location("settings.json"),
		fields...,
	)
	if _, err := configuration.Observe([]releasecontract.Resource{resource}, &fakeHost{}); err == nil {
		t.Fatal("Observe() accepted too many owned JSON fields")
	} else if !strings.Contains(err.Error(), "at most 1024") {
		t.Fatalf("Observe() error = %q", err)
	}
}

func TestObserveBoundsAggregateOwnedJSONPointersPerTarget(t *testing.T) {
	target := location("settings.json")
	first := withJSON(
		resource("json-a", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		target,
		ownedFields(0, 512)...,
	)
	second := withJSON(
		resource("json-b", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		target,
		ownedFields(512, 512)...,
	)
	if _, err := configuration.Observe([]releasecontract.Resource{first, second}, &fakeHost{}); err != nil {
		t.Fatalf("Observe() rejected 1024 aggregate fields: %v", err)
	}
	second.OwnedJSONFields = append(second.OwnedJSONFields, ownedFields(1024, 1)...)
	if _, err := configuration.Observe([]releasecontract.Resource{first, second}, &fakeHost{}); err == nil {
		t.Fatal("Observe() accepted 1025 aggregate fields")
	}
}

func TestObserveAllowsDirectoryResourceAboveJSONTarget(t *testing.T) {
	directory := resource("managed", releasecontract.StrategyEnsureDir, releasecontract.SupportSupported)
	jsonTarget := location("managed/settings.json")
	jsonResource := withJSON(
		resource("json", releasecontract.StrategyJSONKeyMerge, releasecontract.SupportSupported),
		jsonTarget,
		releasecontract.JSONField{Pointer: "/permissions", Desired: `{}`},
	)
	host := &fakeHost{entries: map[domain.Location]hostfs.Entry{
		directory.Target: {Kind: hostfs.EntryDirectory},
		jsonTarget:       {Kind: hostfs.EntryRegular, Content: []byte(`{"permissions":{}}`)},
	}}
	if _, err := configuration.Observe([]releasecontract.Resource{directory, jsonResource}, host); err != nil {
		t.Fatalf("Observe() error = %v", err)
	}
}

type fakeHost struct {
	entries     map[domain.Location]hostfs.Entry
	failures    map[domain.Location]error
	readContent map[domain.Location]bool
	calls       map[domain.Location]int
}

func (host *fakeHost) Inspect(location domain.Location, includeContent bool) (hostfs.Entry, error) {
	if host.readContent == nil {
		host.readContent = make(map[domain.Location]bool)
	}
	if host.calls == nil {
		host.calls = make(map[domain.Location]int)
	}
	host.calls[location]++
	host.readContent[location] = includeContent
	if err := host.failures[location]; err != nil {
		return hostfs.Entry{}, err
	}
	entry, exists := host.entries[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	if entry.Device != 0 && entry.Inode != 0 && entry.BirthSeconds == 0 {
		entry.BirthSeconds = int64(entry.Inode) + 1
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

func withJSON(
	resource releasecontract.Resource,
	target domain.Location,
	fields ...releasecontract.JSONField,
) releasecontract.Resource {
	resource.Target = target
	resource.OwnedJSONFields = fields
	return resource
}

func location(path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: domain.RootOpenCodeConfig, Path: path}
}

func observation(id string, status configuration.Status, reason configuration.Reason) configuration.Observation {
	return configuration.Observation{
		ResourceID: id, ComponentID: "credential-tools",
		Status: status, Reason: reason,
	}
}

func ownedFields(start, count int) []releasecontract.JSONField {
	fields := make([]releasecontract.JSONField, count)
	for index := range fields {
		fields[index] = releasecontract.JSONField{
			Pointer: fmt.Sprintf("/field-%04d", start+index),
			Desired: "null",
		}
	}
	return fields
}
