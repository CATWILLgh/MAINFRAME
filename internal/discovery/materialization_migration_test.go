package discovery_test

import (
	"crypto/sha256"
	"fmt"
	"io/fs"
	"testing"
	"testing/fstest"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestDiscoverAllowsOnlyExactManagedSymlinkToWritableFileMigration(t *testing.T) {
	target := loc(domain.RootCodexConfig, "agents/AGENT.md")
	current := []byte("current\n")
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.agent", Target: target, SourcePath: "dist/AGENT.md",
		Materialization: domain.MaterializationWritableFile,
		SourceSHA256:    fmt.Sprintf("%x", sha256.Sum256(current)),
	}})
	exact := ownershipClaim(
		"component", "component.agent", target, "/releases/old/AGENT.md",
	)
	tests := []struct {
		name   string
		claim  *linkownership.Claim
		link   string
		status domain.OwnershipStatus
	}{
		{name: "exact managed", claim: &exact, link: exact.RawTarget, status: domain.OwnershipManagedPrevious},
		{name: "foreign", link: exact.RawTarget, status: domain.OwnershipConflict},
		{name: "changed target", claim: &exact, link: "/foreign/AGENT.md", status: domain.OwnershipConflict},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			claims := []linkownership.Claim{}
			if test.claim != nil {
				claims = append(claims, *test.claim)
			}
			registry, err := linkownership.New(claims)
			if err != nil {
				t.Fatalf("new registry: %v", err)
			}
			filesystem := fstest.MapFS{
				"source/dist/AGENT.md":          {Data: current, Mode: 0o644},
				"targets/codex/agents/AGENT.md": symlink(test.link),
			}
			got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
			if err != nil {
				t.Fatalf("discover: %v", err)
			}
			artifact := got.Components[0].Artifacts[0]
			if artifact.Ownership != test.status || artifact.RawTarget != test.link ||
				artifact.Materialization != "" {
				t.Fatalf("artifact = %#v", artifact)
			}
		})
	}
}

func TestDiscoverPreservesWritableFileWhenDesiredReturnsToSymlink(t *testing.T) {
	target := loc(domain.RootCodexConfig, "agents/AGENT.md")
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{
		UnitID: "component.agent", Target: target, SourcePath: "dist/AGENT.md",
	}})
	claim := ownershipClaim("component", "component.agent", target, "")
	claim.Materialization = domain.MaterializationWritableFile
	claim.ContentSHA256 = ownershipDigest
	claim.Mode = 0o600
	registry, err := linkownership.New([]linkownership.Claim{claim})
	if err != nil {
		t.Fatalf("new registry: %v", err)
	}
	filesystem := fstest.MapFS{
		"source/dist/AGENT.md":          {Data: []byte("source\n"), Mode: 0o644},
		"targets/codex/agents/AGENT.md": {Data: []byte("local\n"), Mode: fs.FileMode(0o600)},
	}
	got, err := discovery.DiscoverWithOwnership(model, filesystem, validRoots(), registry)
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	if artifact := got.Components[0].Artifacts[0]; artifact.Ownership != domain.OwnershipManagedDrifted {
		t.Fatalf("reverse migration artifact = %#v", artifact)
	}
}
