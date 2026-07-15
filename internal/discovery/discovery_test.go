package discovery_test

import (
	"errors"
	"io/fs"
	"reflect"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
)

func TestDiscoverDesiredClassificationAndPrecedence(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{
		{Target: loc(domain.RootCodexConfig, "absolute"), SourcePath: "dist/absolute", LegacyTargetSuffixes: []domain.ArtifactPath{"dist/absolute"}},
		{Target: loc(domain.RootCodexConfig, "nested/relative"), SourcePath: "dist/relative"},
		{Target: loc(domain.RootCodexConfig, "broken"), SourcePath: "dist/broken", LegacyTargetSuffixes: []domain.ArtifactPath{"dist/broken"}},
		{Target: loc(domain.RootCodexConfig, "legacy"), SourcePath: "dist/current", LegacyTargetSuffixes: []domain.ArtifactPath{"old/legacy"}},
		{Target: loc(domain.RootCodexConfig, "wrong"), SourcePath: "dist/wrong"},
		{Target: loc(domain.RootCodexConfig, "regular"), SourcePath: "dist/regular"},
		{Target: loc(domain.RootCodexConfig, "directory"), SourcePath: "dist/directory"},
		{Target: loc(domain.RootCodexConfig, "absent"), SourcePath: "dist/absent"},
	})
	filesystem := fstest.MapFS{
		"targets/codex/absolute": symlink("/source/dist/absolute"), "source/dist/absolute": file(),
		"targets/codex/nested/relative": symlink("../../../source/dist/relative"), "source/dist/relative": file(),
		"targets/codex/broken":    symlink("/source/dist/broken"),
		"targets/codex/legacy":    symlink("/old/repo/old/legacy"),
		"targets/codex/wrong":     symlink("/other/missing"),
		"targets/codex/regular":   file(),
		"targets/codex/directory": {Mode: fs.ModeDir},
	}
	got, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observedState("component", []domain.Artifact{
		artifact(domain.RootCodexConfig, "absolute", domain.OwnershipManagedExact),
		artifact(domain.RootCodexConfig, "broken", domain.OwnershipManagedDrifted),
		artifact(domain.RootCodexConfig, "directory", domain.OwnershipConflict),
		artifact(domain.RootCodexConfig, "legacy", domain.OwnershipLegacyAdoptable),
		artifact(domain.RootCodexConfig, "nested/relative", domain.OwnershipManagedExact),
		artifact(domain.RootCodexConfig, "regular", domain.OwnershipConflict),
		artifact(domain.RootCodexConfig, "wrong", domain.OwnershipForeign),
	})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverDoesNotStatLegacyOrWrongTargets(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{
		{Target: loc(domain.RootCodexConfig, "legacy"), SourcePath: "dist/legacy", LegacyTargetSuffixes: []domain.ArtifactPath{"old/legacy"}},
		{Target: loc(domain.RootCodexConfig, "wrong"), SourcePath: "dist/wrong"},
	})
	filesystem := &faultFS{
		MapFS: fstest.MapFS{
			"targets/codex/legacy": symlink("/missing/old/legacy"),
			"targets/codex/wrong":  symlink("/missing/wrong"),
		},
		statErr: errors.New("must not stat"),
	}
	got, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observedState("component", []domain.Artifact{
		artifact(domain.RootCodexConfig, "legacy", domain.OwnershipLegacyAdoptable),
		artifact(domain.RootCodexConfig, "wrong", domain.OwnershipForeign),
	})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverLegacyOnlyNeverUsesManagedStatuses(t *testing.T) {
	model := modelWithLegacy(t, []installmodel.LegacyArtifactSpec{
		{Target: loc(domain.RootCodexConfig, "match"), TargetSuffixes: []domain.ArtifactPath{"old/match"}},
		{Target: loc(domain.RootCodexConfig, "wrong"), TargetSuffixes: []domain.ArtifactPath{"old/wrong"}},
		{Target: loc(domain.RootCodexConfig, "regular"), TargetSuffixes: []domain.ArtifactPath{"old/regular"}},
		{Target: loc(domain.RootCodexConfig, "directory"), TargetSuffixes: []domain.ArtifactPath{"old/directory"}},
	})
	filesystem := fstest.MapFS{
		"targets/codex/match":     symlink("/missing/old/match"),
		"targets/codex/wrong":     symlink("/missing/not-old/wrong"),
		"targets/codex/regular":   file(),
		"targets/codex/directory": {Mode: fs.ModeDir},
	}
	got, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observedState("component", []domain.Artifact{
		artifact(domain.RootCodexConfig, "directory", domain.OwnershipForeign),
		artifact(domain.RootCodexConfig, "match", domain.OwnershipLegacyAdoptable),
		artifact(domain.RootCodexConfig, "regular", domain.OwnershipForeign),
		artifact(domain.RootCodexConfig, "wrong", domain.OwnershipForeign),
	})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
	result, err := plan.New(model.Catalog()).Plan(domain.PlanRequest{Observed: got})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	for _, operation := range result.Operations {
		if operation.Kind == domain.OperationRemove {
			t.Fatalf("legacy-only operation must not remove: %#v", operation)
		}
	}
}

func TestDiscoverRejectsInvalidMissingAndCollidingRoots(t *testing.T) {
	model := multiRootModel(t)
	tests := []struct {
		name    string
		roots   discovery.Roots
		message string
	}{
		{name: "invalid source", roots: discovery.Roots{Source: "../source", Targets: targetRoots()}, message: "source"},
		{name: "missing root", roots: discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{domain.RootClaudeConfig: "targets/claude"}}, message: "missing target root"},
		{name: "invalid root ID", roots: discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{"Invalid": "target", domain.RootClaudeConfig: "targets/claude", domain.RootCodexConfig: "targets/codex"}}, message: "root ID"},
		{name: "invalid target root", roots: discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{domain.RootClaudeConfig: "../target", domain.RootCodexConfig: "targets/codex"}}, message: "target root"},
		{name: "exact alias", roots: discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{domain.RootClaudeConfig: "same", domain.RootCodexConfig: "same"}}, message: "collide"},
		{name: "nested alias", roots: discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{domain.RootClaudeConfig: "same", domain.RootCodexConfig: "same/AGENTS.md"}}, message: "collide"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := discovery.Discover(model, fstest.MapFS{}, tt.roots)
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestDiscoverAllowsNestedBindingsWithoutArtifactCollision(t *testing.T) {
	model := multiRootModel(t)
	roots := discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{
		domain.RootClaudeConfig: "same/claude",
		domain.RootCodexConfig:  "same/claude/nested",
	}}
	if _, err := discovery.Discover(model, fstest.MapFS{}, roots); err != nil {
		t.Fatalf("discover: %v", err)
	}
}

func TestDiscoverCopiesTargetBindingsBeforeFilesystemAccess(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{Target: loc(domain.RootCodexConfig, "file"), SourcePath: "dist/file"}})
	targets := map[domain.RootID]domain.ArtifactPath{domain.RootCodexConfig: "targets/codex"}
	filesystem := &faultFS{MapFS: fstest.MapFS{
		"targets/codex/file": symlink("/source/dist/file"), "source/dist/file": file(),
	}}
	filesystem.onLstat = func() { targets[domain.RootCodexConfig] = "mutated" }
	got, err := discovery.Discover(model, filesystem, discovery.Roots{Source: "source", Targets: targets})
	if err != nil || got.Components[0].Artifacts[0].Ownership != domain.OwnershipManagedExact {
		t.Fatalf("observed = %#v, error = %v", got, err)
	}
}

func TestDiscoverOutputIsDeterministicByComponentAndLocation(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: "z", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootCodexConfig, "z"), SourcePath: "dist/z"}, {Target: loc(domain.RootCodexConfig, "a"), SourcePath: "dist/a"}}},
		{ID: "a", Artifacts: []installmodel.ArtifactSpec{{Target: loc(domain.RootClaudeConfig, "file"), SourcePath: "dist/file"}}},
	})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	filesystem := fstest.MapFS{
		"targets/codex/z": symlink("/source/dist/z"), "source/dist/z": file(),
		"targets/codex/a": symlink("/source/dist/a"), "source/dist/a": file(),
		"targets/claude/file": symlink("/source/dist/file"), "source/dist/file": file(),
	}
	first, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	second, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil || !reflect.DeepEqual(first, second) {
		t.Fatalf("second = %#v, error = %v", second, err)
	}
	if first.Components[0].ID != "a" || first.Components[1].Artifacts[0].Location.Path != "a" {
		t.Fatalf("unexpected order: %#v", first)
	}
}

func TestDiscoveryMakesNoPhysicalSymlinkAliasClaim(t *testing.T) {
	model := multiRootModel(t)
	roots := discovery.Roots{Source: "source", Targets: map[domain.RootID]domain.ArtifactPath{
		domain.RootClaudeConfig: "aliases/one",
		domain.RootCodexConfig:  "aliases/two",
	}}
	if _, err := discovery.Discover(model, fstest.MapFS{}, roots); err != nil {
		t.Fatalf("lexically distinct paths must not be rejected: %v", err)
	}
}

func TestDiscoverReturnsContextualFilesystemErrors(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{Target: loc(domain.RootCodexConfig, "file"), SourcePath: "dist/file"}})
	tests := []struct {
		name, message string
		filesystem    *faultFS
	}{
		{name: "lstat", message: "inspect artifact", filesystem: &faultFS{MapFS: fstest.MapFS{}, lstatErr: errors.New("denied")}},
		{name: "readlink", message: "read link", filesystem: &faultFS{MapFS: fstest.MapFS{"targets/codex/file": symlink("/source/dist/file")}, readlinkErr: errors.New("denied")}},
		{name: "target stat", message: "inspect link target", filesystem: &faultFS{MapFS: fstest.MapFS{"targets/codex/file": symlink("/source/dist/file")}, statErr: errors.New("denied")}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := discovery.Discover(model, tt.filesystem, validRoots())
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestDiscoverRejectsNilFilesystem(t *testing.T) {
	model := modelWithArtifacts(t, []installmodel.ArtifactSpec{{Target: loc(domain.RootCodexConfig, "file"), SourcePath: "dist/file"}})
	_, err := discovery.Discover(model, nil, validRoots())
	if err == nil || !strings.Contains(err.Error(), "filesystem") {
		t.Fatalf("expected filesystem error, got %v", err)
	}
}

type faultFS struct {
	fstest.MapFS
	lstatErr, readlinkErr, statErr error
	onLstat                        func()
}

func (filesystem *faultFS) Lstat(name string) (fs.FileInfo, error) {
	if filesystem.onLstat != nil {
		filesystem.onLstat()
	}
	if filesystem.lstatErr != nil {
		return nil, filesystem.lstatErr
	}
	return filesystem.MapFS.Lstat(name)
}

func (filesystem *faultFS) ReadLink(name string) (string, error) {
	if filesystem.readlinkErr != nil {
		return "", filesystem.readlinkErr
	}
	return filesystem.MapFS.ReadLink(name)
}

func (filesystem *faultFS) Stat(name string) (fs.FileInfo, error) {
	if filesystem.statErr != nil {
		return nil, filesystem.statErr
	}
	return filesystem.MapFS.Stat(name)
}

func modelWithArtifacts(t *testing.T, artifacts []installmodel.ArtifactSpec) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{{ID: "component", Artifacts: artifacts}})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	return model
}

func modelWithLegacy(t *testing.T, artifacts []installmodel.LegacyArtifactSpec) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{{ID: "component", LegacyArtifacts: artifacts}})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	return model
}

func multiRootModel(t *testing.T) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{{ID: "component", Artifacts: []installmodel.ArtifactSpec{
		{Target: loc(domain.RootClaudeConfig, "AGENTS.md"), SourcePath: "dist/claude"},
		{Target: loc(domain.RootCodexConfig, "AGENTS.md"), SourcePath: "dist/codex"},
	}}})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	return model
}

func validRoots() discovery.Roots {
	return discovery.Roots{Source: "source", Targets: targetRoots()}
}

func targetRoots() map[domain.RootID]domain.ArtifactPath {
	return map[domain.RootID]domain.ArtifactPath{domain.RootCodexConfig: "targets/codex", domain.RootClaudeConfig: "targets/claude"}
}

func loc(root domain.RootID, path domain.ArtifactPath) domain.Location {
	return domain.Location{Root: root, Path: path}
}

func artifact(root domain.RootID, path domain.ArtifactPath, ownership domain.OwnershipStatus) domain.Artifact {
	return domain.Artifact{Location: loc(root, path), Ownership: ownership}
}

func observedState(id domain.ComponentID, artifacts []domain.Artifact) domain.ObservedState {
	return domain.ObservedState{Components: []domain.ObservedComponent{{ID: id, Artifacts: artifacts}}}
}

func symlink(target string) *fstest.MapFile {
	return &fstest.MapFile{Mode: fs.ModeSymlink, Data: []byte(target)}
}

func file() *fstest.MapFile {
	return &fstest.MapFile{Data: []byte("data")}
}
