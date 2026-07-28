package credentialmigration

import (
	"encoding/json"
	"errors"
	"io/fs"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestInspectLegacyIndexesClassifiesWithoutReturningContent(t *testing.T) {
	release := legacyReleaseFixture()
	canary := "legacy-private-canary"
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{
			release.Resources[0].Target: {
				Kind: hostfs.EntryRegular,
				Mode: 0o600, Content: []byte("claude-template"),
			},
			release.Resources[1].Target: {
				Kind: hostfs.EntryRegular,
				Mode: 0o600, Content: []byte(canary),
			},
			release.Resources[2].Target: {
				Kind: hostfs.EntrySymlink,
				Mode: 0o777, SymlinkTargetPath: "/private/target",
			},
		},
		errors: map[domain.Location]error{
			release.Resources[3].Target: fs.ErrNotExist,
		},
	}

	inventory, err := InspectLegacyIndexes(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyIndexes() error = %v", err)
	}
	got := make([]IndexState, len(inventory.Indexes))
	for index, item := range inventory.Indexes {
		got[index] = item.State
	}
	want := []IndexState{
		IndexPresent,
		IndexPresent,
		IndexUnsafe,
		IndexMissing,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("states = %v, want %v", got, want)
	}
	if !inventory.Indexes[0].MatchesCurrentTemplate ||
		inventory.Indexes[1].MatchesCurrentTemplate {
		t.Fatalf("template matches = %#v", inventory.Indexes)
	}
	readiness := []Readiness{
		inventory.Indexes[0].MigrationReadiness,
		inventory.Indexes[1].MigrationReadiness,
		inventory.Indexes[2].MigrationReadiness,
		inventory.Indexes[3].MigrationReadiness,
	}
	wantReadiness := []Readiness{
		ReadinessNoTransferRequired,
		ReadinessManualTransferRequired,
		ReadinessBlocked,
		ReadinessNoTransferRequired,
	}
	if !reflect.DeepEqual(readiness, wantReadiness) {
		t.Fatalf("readiness = %v, want %v", readiness, wantReadiness)
	}
	if inventory.MigrationReadiness != ReadinessBlocked {
		t.Fatalf(
			"migration readiness = %q, want %q",
			inventory.MigrationReadiness,
			ReadinessBlocked,
		)
	}
	payload, err := json.Marshal(inventory)
	if err != nil {
		t.Fatalf("marshal inventory: %v", err)
	}
	if strings.Contains(string(payload), canary) ||
		strings.Contains(string(payload), "/private/target") {
		t.Fatalf("inventory exposed inspected content: %s", payload)
	}
}

func TestInspectLegacyIndexesReducesEveryMixedReadinessCombination(
	t *testing.T,
) {
	states := []Readiness{
		ReadinessNoTransferRequired,
		ReadinessManualTransferRequired,
		ReadinessBlocked,
	}
	for _, first := range states {
		for _, second := range states {
			for _, third := range states {
				for _, fourth := range states {
					readiness := []Readiness{first, second, third, fourth}
					t.Run(strings.Join(readinessStrings(readiness), "-"), func(t *testing.T) {
						release := legacyReleaseFixture()
						inspector := legacyInspectorForReadiness(release, readiness)
						inventory, err := InspectLegacyIndexes(release, inspector)
						if err != nil {
							t.Fatalf("InspectLegacyIndexes() error = %v", err)
						}
						want := expectedOverallReadiness(readiness)
						if inventory.MigrationReadiness != want {
							t.Fatalf(
								"migration readiness = %q, want %q",
								inventory.MigrationReadiness,
								want,
							)
						}
					})
				}
			}
		}
	}
}

func TestInspectLegacyIndexesRejectsUnsafeModesAndInspectionFailures(
	t *testing.T,
) {
	release := legacyReleaseFixture()
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{},
		errors:  map[domain.Location]error{},
	}
	for index, resource := range release.Resources {
		inspector.entries[resource.Target] = hostfs.Entry{
			Kind: hostfs.EntryRegular,
			Mode: 0o600, Content: append([]byte(nil), resource.SourceContent...),
		}
		if index == 0 {
			inspector.entries[resource.Target] = hostfs.Entry{
				Kind: hostfs.EntryRegular,
				Mode: 0o644, Content: []byte("public"),
			}
		}
		if index == 1 {
			inspector.errors[resource.Target] = errors.New(
				"legacy-private-canary",
			)
		}
	}

	inventory, err := InspectLegacyIndexes(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyIndexes() error = %v", err)
	}
	if inventory.Indexes[0].UnsafeReason != ReasonUnsafeMode ||
		inventory.Indexes[1].UnsafeReason != ReasonInspectionFailed {
		t.Fatalf("unsafe inventory = %#v", inventory.Indexes)
	}
	payload, err := json.Marshal(inventory)
	if err != nil {
		t.Fatalf("marshal inventory: %v", err)
	}
	if strings.Contains(string(payload), "legacy-private-canary") {
		t.Fatalf("inventory exposed inspection error: %s", payload)
	}
}

func TestInspectLegacyIndexesRequiresExactReleaseResources(t *testing.T) {
	release := legacyReleaseFixture()
	release.Resources = release.Resources[:3]

	_, err := InspectLegacyIndexes(release, &legacyInspectorFixture{})
	if err == nil || strings.Contains(err.Error(), "antigravity") {
		t.Fatalf("missing resource error = %v", err)
	}
}

func legacyInspectorForReadiness(
	release releasecontract.Release,
	readiness []Readiness,
) *legacyInspectorFixture {
	fixture := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{},
		errors:  map[domain.Location]error{},
	}
	for index, state := range readiness {
		resource := release.Resources[index]
		switch state {
		case ReadinessNoTransferRequired:
			fixture.errors[resource.Target] = fs.ErrNotExist
		case ReadinessManualTransferRequired:
			fixture.entries[resource.Target] = hostfs.Entry{
				Kind: hostfs.EntryRegular,
				Mode: 0o600, Content: []byte("divergent"),
			}
		case ReadinessBlocked:
			fixture.entries[resource.Target] = hostfs.Entry{
				Kind: hostfs.EntrySymlink,
				Mode: 0o777,
			}
		}
	}
	return fixture
}

func expectedOverallReadiness(readiness []Readiness) Readiness {
	result := ReadinessNoTransferRequired
	for _, state := range readiness {
		if state == ReadinessBlocked {
			return ReadinessBlocked
		}
		if state == ReadinessManualTransferRequired {
			result = ReadinessManualTransferRequired
		}
	}
	return result
}

func readinessStrings(readiness []Readiness) []string {
	result := make([]string, len(readiness))
	for index, state := range readiness {
		result[index] = string(state)
	}
	return result
}

type legacyInspectorFixture struct {
	entries map[domain.Location]hostfs.Entry
	errors  map[domain.Location]error
}

func (fixture *legacyInspectorFixture) Inspect(
	location domain.Location,
	includeContent bool,
) (hostfs.Entry, error) {
	if !includeContent {
		return hostfs.Entry{}, errors.New("content inspection was not requested")
	}
	if err := fixture.errors[location]; err != nil {
		return hostfs.Entry{}, err
	}
	return fixture.entries[location], nil
}

func legacyReleaseFixture() releasecontract.Release {
	resources := []struct {
		component domain.ComponentID
		id        string
		root      domain.RootID
		template  string
	}{
		{
			domain.ComponentClaudeCode,
			"claude-code.credentials-index",
			domain.RootClaudeConfig,
			"claude-template",
		},
		{
			domain.ComponentCodex,
			"codex.credentials-index",
			domain.RootCodexConfig,
			"codex-template",
		},
		{
			domain.ComponentOpenCode,
			"opencode.credentials-index",
			domain.RootOpenCodeConfig,
			"opencode-template",
		},
		{
			domain.ComponentAntigravity2,
			"antigravity-2.credentials-index",
			domain.RootAntigravityData,
			"antigravity-template",
		},
	}
	release := releasecontract.Release{
		ID:          "release-a",
		IndexSHA256: strings.Repeat("a", 64),
	}
	for _, resource := range resources {
		release.Resources = append(release.Resources, releasecontract.Resource{
			ID:          resource.id,
			ComponentID: resource.component,
			Strategy:    releasecontract.StrategySeedIfAbsent,
			Target: domain.Location{
				Root: resource.root,
				Path: "credentials-index.md",
			},
			SourceContent: []byte(resource.template),
		})
	}
	return release
}
