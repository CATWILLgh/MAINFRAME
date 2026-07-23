package main

import (
	"io/fs"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestDiagnosticsObservationFiltersExactResourcesBeforeHostReads(t *testing.T) {
	resources := []releasecontract.Resource{
		diagnosticsObservationGenericResource(),
		diagnosticsObservationExactResource(
			domain.ComponentClaudeCode,
			domain.RootClaudeConfig,
		),
		diagnosticsObservationExactResource(
			domain.ComponentCodex,
			domain.RootCodexConfig,
		),
	}
	tests := map[string]struct {
		request application.Request
		want    []domain.Location
	}{
		"static preview": {
			want: []domain.Location{resources[0].Target},
		},
		"unconfigured request": {
			request: application.Request{
				Components: []domain.ComponentID{domain.ComponentCodex},
			},
			want: []domain.Location{resources[0].Target},
		},
		"configured selected adapter": {
			request: application.Request{
				Components:  []domain.ComponentID{domain.ComponentCodex},
				Diagnostics: diagnostics.Desired{Configured: true},
			},
			want: []domain.Location{resources[0].Target, resources[2].Target},
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			host := &diagnosticsObservationHost{}
			release := releasecontract.Release{
				Model:     previewOwnershipModel(t),
				Resources: resources,
			}
			_, err := buildInspectedService(
				"", release, "", nil, hostlayout.Layout{}, host,
				domain.ObservedState{},
				diagnosticsObservationScopeFor(test.request),
			)
			if err != nil {
				t.Fatalf("buildInspectedService() error = %v", err)
			}
			if !sameLocations(host.locations, test.want) {
				t.Fatalf("inspected locations = %#v, want %#v", host.locations, test.want)
			}
		})
	}
}

type diagnosticsObservationHost struct {
	locations []domain.Location
}

func (host *diagnosticsObservationHost) Inspect(
	location domain.Location,
	_ bool,
) (hostfs.Entry, error) {
	host.locations = append(host.locations, location)
	return hostfs.Entry{}, fs.ErrNotExist
}

func diagnosticsObservationGenericResource() releasecontract.Resource {
	return releasecontract.Resource{
		ID:          "claude-code.cache",
		ComponentID: domain.ComponentClaudeCode,
		Strategy:    releasecontract.StrategyEnsureDir,
		Target: domain.Location{
			Root: domain.RootClaudeConfig,
			Path: "cache",
		},
		Observation: releasecontract.SupportSupported,
		Apply:       releasecontract.SupportUnimplemented,
	}
}

func diagnosticsObservationExactResource(
	component domain.ComponentID,
	root domain.RootID,
) releasecontract.Resource {
	return releasecontract.Resource{
		ID:          string(component) + ".diagnostics",
		ComponentID: component,
		Strategy:    releasecontract.StrategyExactJSONDocument,
		SourcePath:  "bundles/" + domain.ArtifactPath(component) + "/diagnostics.json",
		Target: domain.Location{
			Root: root,
			Path: "mainframe/diagnostics.json",
		},
		Observation:       releasecontract.SupportSupported,
		Apply:             releasecontract.SupportSupported,
		ExactJSONExemplar: `{"events":false,"feedback":false,"schema_version":1}`,
	}
}

func sameLocations(left, right []domain.Location) bool {
	if len(left) != len(right) {
		return false
	}
	seen := make(map[domain.Location]int, len(left))
	for _, location := range left {
		seen[location]++
	}
	for _, location := range right {
		seen[location]--
	}
	for _, count := range seen {
		if count != 0 {
			return false
		}
	}
	return true
}
