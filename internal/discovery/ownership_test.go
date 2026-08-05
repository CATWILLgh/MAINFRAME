package discovery_test

import (
	"crypto/sha256"
	"fmt"
	"io/fs"
	"reflect"
	"testing"
	"testing/fstest"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestDiscoverWithOwnershipClassifiesWritableFileContent(t *testing.T) {
	target := loc(domain.RootCodexConfig, "AGENTS.md")
	installed := []byte("installed\n")
	current := []byte("current\n")
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.instructions", Target: target,
		SourcePath: "dist/AGENTS.md", Materialization: domain.MaterializationWritableFile,
		SourceSHA256: fmt.Sprintf("%x", sha256.Sum256(current)),
	}})
	claim := ownershipClaim("component", "component.instructions", target, "")
	claim.Materialization = domain.MaterializationWritableFile
	claim.ContentSHA256 = fmt.Sprintf("%x", sha256.Sum256(installed))
	claim.Mode = 0o600
	registry, err := linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	tests := []struct {
		name    string
		content []byte
		mode    uint32
		status  domain.OwnershipStatus
	}{
		{name: "previous", content: installed, mode: 0o600, status: domain.OwnershipManagedPrevious},
		{name: "drifted content", content: []byte("local\n"), mode: 0o600, status: domain.OwnershipManagedDrifted},
		{name: "drifted mode", content: installed, mode: 0o400, status: domain.OwnershipManagedDrifted},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			filesystem := fstest.MapFS{
				"source/dist/AGENTS.md":   {Data: current, Mode: 0o644},
				"targets/codex/AGENTS.md": {Data: test.content, Mode: fs.FileMode(test.mode)},
			}
			got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
			if err != nil {
				t.Fatalf("discover: %v", err)
			}
			artifact := got.Components[0].Artifacts[0]
			if artifact.Ownership != test.status || artifact.Materialization != domain.MaterializationWritableFile ||
				(test.mode == 0o600 && artifact.ContentSHA256 == "") || artifact.Mode != test.mode {
				t.Fatalf("artifact = %#v", artifact)
			}
		})
	}

	claim.ContentSHA256 = fmt.Sprintf("%x", sha256.Sum256(current))
	registry, err = linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new current registry: %v", err)
	}
	filesystem := fstest.MapFS{
		"source/dist/AGENTS.md":   {Data: current, Mode: 0o644},
		"targets/codex/AGENTS.md": {Data: current, Mode: 0o600},
	}
	got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
	if err != nil || got.Components[0].Artifacts[0].Ownership != domain.OwnershipManagedExact {
		t.Fatalf("exact observation = %#v, error = %v", got, err)
	}
}

const ownershipDigest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

func TestDiscoverWithOwnershipRequiresExactClaimAndRawTarget(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.instructions", Target: loc(domain.RootCodexConfig, "AGENTS.md"),
		SourcePath: "dist/AGENTS.md", LegacyTargetSuffixes: []domain.ArtifactPath{"old/AGENTS.md"},
	}})
	filesystem := fstest.MapFS{
		"targets/codex/AGENTS.md": symlink("/source/dist/AGENTS.md"),
		"source/dist/AGENTS.md":   file(),
	}
	tests := []struct {
		name   string
		claims []linkownership.Claim
		status domain.OwnershipStatus
	}{
		{name: "registry-less", status: domain.OwnershipExactAdoptable},
		{name: "exact", claims: []linkownership.Claim{ownershipClaim("component", "component.instructions", loc(domain.RootCodexConfig, "AGENTS.md"), "/source/dist/AGENTS.md")}, status: domain.OwnershipManagedExact},
		{name: "changed raw target", claims: []linkownership.Claim{ownershipClaim("component", "component.instructions", loc(domain.RootCodexConfig, "AGENTS.md"), "/source/old/AGENTS.md")}, status: domain.OwnershipManagedDrifted},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			registry, err := linkownership.New(test.claims)
			if err != nil {
				t.Fatalf("new registry: %v", err)
			}
			got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
			if err != nil {
				t.Fatalf("discover: %v", err)
			}
			artifact := got.Components[0].Artifacts[0]
			if artifact.Ownership != test.status || artifact.RawTarget != "/source/dist/AGENTS.md" || artifact.UnitID != "component.instructions" {
				t.Fatalf("artifact = %#v", artifact)
			}
		})
	}
}

func TestDiscoverWithOwnershipFindsPreviousAndAbsentCatalogUnits(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.instructions", Target: loc(domain.RootCodexConfig, "AGENTS.md"), SourcePath: "dist/AGENTS.md",
	}})
	previous := ownershipClaim("component", "component.instructions", loc(domain.RootCodexConfig, "AGENTS.md"), "/releases/old/AGENTS.md")
	retired := ownershipClaim("retired", "retired.link", loc(domain.RootCodexConfig, "retired"), "/releases/old/retired")
	registry, err := linkownership.New([]linkownership.Claim{previous, retired})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	filesystem := fstest.MapFS{
		"targets/codex/AGENTS.md": symlink(previous.RawTarget),
		"targets/codex/retired":   symlink(retired.RawTarget),
	}
	got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := domain.ObservedState{Components: []domain.ObservedComponent{
		{ID: "component", Artifacts: []domain.Artifact{{Location: previous.Target, UnitID: previous.UnitID, Ownership: domain.OwnershipManagedPrevious, RawTarget: previous.RawTarget}}},
		{ID: "retired", Artifacts: []domain.Artifact{{Location: retired.Target, UnitID: retired.UnitID, Ownership: domain.OwnershipManagedPrevious, RawTarget: retired.RawTarget}}},
	}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverWithOwnershipSurfacesMissingClaimedLink(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.instructions", Target: loc(domain.RootCodexConfig, "AGENTS.md"),
		SourcePath: "dist/AGENTS.md",
	}})
	claim := ownershipClaim(
		"component", "component.instructions",
		loc(domain.RootCodexConfig, "AGENTS.md"), "/releases/old/AGENTS.md",
	)
	registry, err := linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}

	got, err := discovery.DiscoverWithOwnership(model, fstest.MapFS{}, validRoots(), registry)
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := domain.Artifact{
		Location: claim.Target, UnitID: claim.UnitID,
		Ownership: domain.OwnershipManagedMissing, RawTarget: claim.RawTarget,
	}
	if len(got.Components) != 1 || len(got.Components[0].Artifacts) != 1 ||
		!reflect.DeepEqual(got.Components[0].Artifacts[0], want) {
		t.Fatalf("observed = %#v, want artifact %#v", got, want)
	}
}

func TestDiscoverWithOwnershipSurfacesClaimedNonLinkAsDrifted(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.instructions", Target: loc(domain.RootCodexConfig, "AGENTS.md"),
		SourcePath: "dist/AGENTS.md",
	}})
	claim := ownershipClaim(
		"component", "component.instructions",
		loc(domain.RootCodexConfig, "AGENTS.md"), "/releases/old/AGENTS.md",
	)
	registry, err := linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	filesystem := fstest.MapFS{"targets/codex/AGENTS.md": file()}

	got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := domain.Artifact{
		Location: claim.Target, UnitID: claim.UnitID,
		Ownership: domain.OwnershipManagedDrifted,
	}
	if len(got.Components) != 1 || len(got.Components[0].Artifacts) != 1 ||
		!reflect.DeepEqual(got.Components[0].Artifacts[0], want) {
		t.Fatalf("observed = %#v, want artifact %#v", got, want)
	}
}

func TestDiscoverWithOwnershipSurfacesRetiredClaimedNonLink(t *testing.T) {
	model := modelWithArtifacts(t, nil)
	claim := ownershipClaim(
		"retired", "retired.instructions",
		loc(domain.RootCodexConfig, "retired"), "/releases/old/retired",
	)
	registry, err := linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	filesystem := fstest.MapFS{"targets/codex/retired": file()}

	got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	if len(got.Components) != 1 || len(got.Components[0].Artifacts) != 1 ||
		got.Components[0].Artifacts[0].Ownership != domain.OwnershipManagedDrifted ||
		got.Components[0].Artifacts[0].UnitID != claim.UnitID {
		t.Fatalf("observed = %#v", got)
	}
}

func ownershipClaim(component domain.ComponentID, unit string, target domain.Location, raw string) linkownership.Claim {
	return linkownership.Claim{
		UnitID: unit, ComponentID: component, Target: target, RawTarget: raw,
		ReleaseID: "old-release", IndexSHA256: ownershipDigest,
	}
}
