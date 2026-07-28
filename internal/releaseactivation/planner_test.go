package releaseactivation_test

import (
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/releaseactivation"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestBuildPreviewInstallsOnlyTheReleaseLauncher(t *testing.T) {
	fixture := activationFixture(t)
	foreignClaim := linkownership.Claim{
		UnitID: "opencode.agents", ComponentID: domain.ComponentOpenCode,
		Target: domain.Location{
			Root: domain.RootOpenCodeConfig,
			Path: "AGENTS.md",
		},
		RawTarget: "/unrelated",
		ReleaseID: "old-release", IndexSHA256: strings.Repeat("b", 64),
	}
	registry, err := linkownership.New([]linkownership.Claim{foreignClaim})
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}

	preview, err := releaseactivation.BuildPreview(
		fixture.release,
		fixture.filesystem,
		fixture.roots,
		registry,
	)
	if err != nil {
		t.Fatalf("BuildPreview() error = %v", err)
	}
	if len(preview.Plan.Operations) != 1 {
		t.Fatalf("operations = %#v", preview.Plan.Operations)
	}
	operation := preview.Plan.Operations[0]
	if operation.ComponentID != "mainframe-cli" ||
		operation.UnitID != "mainframe-cli.binary" ||
		operation.Kind != domain.OperationInstall ||
		operation.Artifact.Location != launcherLocation() {
		t.Fatalf("operation = %#v", operation)
	}
}

func TestBuildPreviewPlansExactVersionSwitchAndRollback(t *testing.T) {
	fixture := activationFixture(t)
	oldTarget := filepath.Join(fixture.oldReleaseRoot, "bin", "mainframe")
	if err := os.MkdirAll(filepath.Dir(fixture.launcher), 0o700); err != nil {
		t.Fatalf("mkdir launcher parent: %v", err)
	}
	if err := os.Symlink(oldTarget, fixture.launcher); err != nil {
		t.Fatalf("create old launcher: %v", err)
	}
	registry, err := linkownership.New([]linkownership.Claim{{
		UnitID: "mainframe-cli.binary", ComponentID: "mainframe-cli",
		Target: launcherLocation(), RawTarget: oldTarget,
		ReleaseID: "old-release", IndexSHA256: strings.Repeat("b", 64),
	}})
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}

	preview, err := releaseactivation.BuildPreview(
		fixture.release,
		fixture.filesystem,
		fixture.roots,
		registry,
	)
	if err != nil {
		t.Fatalf("BuildPreview() error = %v", err)
	}
	if len(preview.Plan.Operations) != 1 ||
		preview.Plan.Operations[0].Kind != domain.OperationReplace {
		t.Fatalf("operations = %#v", preview.Plan.Operations)
	}
}

func TestBuildPreviewReturnsNoOpForExactActiveVersion(t *testing.T) {
	fixture := activationFixture(t)
	target := filepath.Join(
		string(filepath.Separator),
		string(fixture.roots.Source),
		"bin",
		"mainframe",
	)
	if err := os.MkdirAll(filepath.Dir(fixture.launcher), 0o700); err != nil {
		t.Fatalf("mkdir launcher parent: %v", err)
	}
	if err := os.Symlink(target, fixture.launcher); err != nil {
		t.Fatalf("create launcher: %v", err)
	}
	registry, err := linkownership.New([]linkownership.Claim{{
		UnitID: "mainframe-cli.binary", ComponentID: "mainframe-cli",
		Target: launcherLocation(), RawTarget: target,
		ReleaseID:   fixture.release.ID,
		IndexSHA256: fixture.release.IndexSHA256,
	}})
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}

	preview, err := releaseactivation.BuildPreview(
		fixture.release,
		fixture.filesystem,
		fixture.roots,
		registry,
	)
	if err != nil {
		t.Fatalf("BuildPreview() error = %v", err)
	}
	if len(preview.Plan.Operations) != 0 {
		t.Fatalf("operations = %#v, want no-op", preview.Plan.Operations)
	}
}

func TestBuildPreviewRejectsForeignLauncher(t *testing.T) {
	fixture := activationFixture(t)
	if err := os.MkdirAll(filepath.Dir(fixture.launcher), 0o700); err != nil {
		t.Fatalf("mkdir launcher parent: %v", err)
	}
	if err := os.Symlink("/foreign/mainframe", fixture.launcher); err != nil {
		t.Fatalf("create foreign launcher: %v", err)
	}
	registry, err := linkownership.New(nil)
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}

	preview, err := releaseactivation.BuildPreview(
		fixture.release,
		fixture.filesystem,
		fixture.roots,
		registry,
	)
	if err != nil {
		t.Fatalf("BuildPreview() error = %v", err)
	}
	if len(preview.Plan.Operations) != 1 ||
		preview.Plan.Operations[0].Kind != domain.OperationConflict {
		t.Fatalf("operations = %#v", preview.Plan.Operations)
	}
}

func TestBuildPreviewRejectsUnexpectedLauncherContract(t *testing.T) {
	fixture := activationFixture(t)
	model, err := installmodel.New([]installmodel.ComponentSpec{{
		ID: "mainframe-cli",
		Artifacts: []installmodel.ArtifactSpec{{
			UnitID:     "mainframe-cli.binary",
			Target:     launcherLocation(),
			SourcePath: "unexpected/mainframe",
		}},
	}})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	fixture.release.Model = model
	registry, err := linkownership.New(nil)
	if err != nil {
		t.Fatalf("linkownership.New() error = %v", err)
	}

	if _, err := releaseactivation.BuildPreview(
		fixture.release,
		fixture.filesystem,
		fixture.roots,
		registry,
	); err == nil {
		t.Fatal("BuildPreview() accepted an unexpected launcher source")
	}
}

type activationTestFixture struct {
	release        releasecontract.Release
	filesystem     fs.ReadLinkFS
	roots          discovery.Roots
	launcher       string
	oldReleaseRoot string
}

func activationFixture(t *testing.T) activationTestFixture {
	t.Helper()
	root := canonicalTemp(t)
	releaseRoot := filepath.Join(root, "release")
	oldReleaseRoot := filepath.Join(root, "old-release")
	launcher := filepath.Join(root, "home", ".local", "bin", "mainframe")
	for _, binary := range []string{
		filepath.Join(releaseRoot, "bin", "mainframe"),
		filepath.Join(oldReleaseRoot, "bin", "mainframe"),
	} {
		if err := os.MkdirAll(filepath.Dir(binary), 0o700); err != nil {
			t.Fatalf("mkdir release bin: %v", err)
		}
		if err := os.WriteFile(binary, []byte("binary\n"), 0o700); err != nil {
			t.Fatalf("write release binary: %v", err)
		}
	}
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{
			ID: "mainframe-cli",
			Artifacts: []installmodel.ArtifactSpec{{
				UnitID:     "mainframe-cli.binary",
				Target:     launcherLocation(),
				SourcePath: "bin/mainframe",
			}},
		},
		{
			ID: domain.ComponentOpenCode,
			Artifacts: []installmodel.ArtifactSpec{{
				UnitID: "opencode.agents",
				Target: domain.Location{
					Root: domain.RootOpenCodeConfig,
					Path: "AGENTS.md",
				},
				SourcePath: "bundles/opencode/AGENTS.md",
			}},
		},
	})
	if err != nil {
		t.Fatalf("installmodel.New() error = %v", err)
	}
	filesystem, ok := os.DirFS("/").(fs.ReadLinkFS)
	if !ok {
		t.Fatal("host filesystem does not support links")
	}
	return activationTestFixture{
		release: releasecontract.Release{
			ID: "new-release", IndexSHA256: strings.Repeat("a", 64),
			Model: model,
		},
		filesystem: filesystem,
		roots: discovery.Roots{
			Source: absoluteArtifactPath(releaseRoot),
			Targets: map[domain.RootID]domain.ArtifactPath{
				domain.RootUserBin: absoluteArtifactPath(
					filepath.Dir(launcher),
				),
			},
		},
		launcher:       launcher,
		oldReleaseRoot: oldReleaseRoot,
	}
}

func launcherLocation() domain.Location {
	return domain.Location{
		Root: domain.RootUserBin,
		Path: "mainframe",
	}
}

func absoluteArtifactPath(path string) domain.ArtifactPath {
	return domain.ArtifactPath(
		strings.TrimPrefix(filepath.ToSlash(path), "/"),
	)
}

func canonicalTemp(t *testing.T) string {
	t.Helper()
	path, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("canonicalize temp: %v", err)
	}
	return path
}
