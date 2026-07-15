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

func TestDiscoverClassifiesLinksAndConflicts(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{
		{HomePath: "exact-absolute", SourcePath: "dist/exact-absolute"},
		{HomePath: "nested/exact-relative", SourcePath: "dist/exact-relative"},
		{HomePath: "exact-broken", SourcePath: "dist/exact-broken"},
		{HomePath: "wrong-live", SourcePath: "dist/wrong-live"},
		{HomePath: "wrong-broken", SourcePath: "dist/wrong-broken"},
		{HomePath: "regular", SourcePath: "dist/regular"},
		{HomePath: "directory", SourcePath: "dist/directory"},
		{HomePath: "absent", SourcePath: "dist/absent"},
	})
	filesystem := fstest.MapFS{
		"home/exact-absolute":        symlink("/source/dist/exact-absolute"),
		"source/dist/exact-absolute": file(),
		"home/nested/exact-relative": symlink("../../source/dist/exact-relative"),
		"source/dist/exact-relative": file(),
		"home/exact-broken":          symlink("/source/dist/exact-broken"),
		"home/wrong-live":            symlink("/other/live"),
		"other/live":                 file(),
		"home/wrong-broken":          symlink("/other/missing"),
		"home/regular":               file(),
		"home/directory":             {Mode: fs.ModeDir},
	}

	got, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observed("component", []domain.Artifact{
		{Path: "directory", Ownership: domain.OwnershipConflict},
		{Path: "exact-absolute", Ownership: domain.OwnershipManagedExact},
		{Path: "exact-broken", Ownership: domain.OwnershipManagedDrifted},
		{Path: "nested/exact-relative", Ownership: domain.OwnershipManagedExact},
		{Path: "regular", Ownership: domain.OwnershipConflict},
		{Path: "wrong-broken", Ownership: domain.OwnershipForeign},
		{Path: "wrong-live", Ownership: domain.OwnershipForeign},
	})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverLegacySuffixIsSegmentAware(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{
		{HomePath: "legacy", SourcePath: "dist/tool/file", LegacyTargetSuffixes: []domain.ArtifactPath{"dist/tool/file"}},
		{HomePath: "lookalike", SourcePath: "dist/tool/lookalike", LegacyTargetSuffixes: []domain.ArtifactPath{"dist/tool/lookalike"}},
	})
	filesystem := fstest.MapFS{
		"home/legacy":                     symlink("/old/repo/dist/tool/file"),
		"old/repo/dist/tool/file":         file(),
		"home/lookalike":                  symlink("/old/repo/notdist/tool/lookalike"),
		"old/repo/notdist/tool/lookalike": file(),
	}

	got, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observed("component", []domain.Artifact{
		{Path: "legacy", Ownership: domain.OwnershipLegacyAdoptable},
		{Path: "lookalike", Ownership: domain.OwnershipForeign},
	})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverMixedArtifactsAreDeterministic(t *testing.T) {
	model, err := installmodel.New([]installmodel.ComponentSpec{
		{ID: domain.ComponentOpenCode, Artifacts: []installmodel.ArtifactSpec{{HomePath: ".config/opencode/AGENTS.md", SourcePath: "dist/opencode/AGENTS.md"}}},
		{ID: domain.ComponentCodex, Artifacts: []installmodel.ArtifactSpec{{HomePath: ".codex/AGENTS.md", SourcePath: "dist/codex/AGENTS.md"}}},
		{ID: domain.ComponentClaudeCode, Artifacts: []installmodel.ArtifactSpec{{HomePath: ".claude/CLAUDE.md", SourcePath: "dist/claude-code/CLAUDE.md"}}},
	})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	filesystem := fstest.MapFS{
		"home/.config/opencode/AGENTS.md": symlink("/source/dist/opencode/AGENTS.md"), "source/dist/opencode/AGENTS.md": file(),
		"home/.codex/AGENTS.md": symlink("/source/dist/codex/AGENTS.md"), "source/dist/codex/AGENTS.md": file(),
		"home/.claude/CLAUDE.md": symlink("/source/dist/claude-code/CLAUDE.md"), "source/dist/claude-code/CLAUDE.md": file(),
	}
	first, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	second, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil || !reflect.DeepEqual(first, second) {
		t.Fatalf("second discovery = %#v, error = %v", second, err)
	}
	wantOrder := []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentCodex, domain.ComponentOpenCode}
	for i, component := range first.Components {
		if component.ID != wantOrder[i] {
			t.Fatalf("component[%d] = %q, want %q", i, component.ID, wantOrder[i])
		}
	}
}

func TestDiscoveredStateProducesNoDuplicateOperations(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{{HomePath: "artifact", SourcePath: "dist/artifact"}})
	filesystem := fstest.MapFS{"home/artifact": symlink("/source/dist/artifact"), "source/dist/artifact": file()}
	state, err := discovery.Discover(model, filesystem, validRoots())
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	result, err := plan.New(model.Catalog()).Plan(domain.PlanRequest{Observed: state})
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	if len(result.Operations) != 1 || result.Operations[0].Kind != domain.OperationRemove {
		t.Fatalf("operations = %#v", result.Operations)
	}
}

func TestDiscoverRejectsInvalidRootsAndEscapingLink(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{{HomePath: "artifact", SourcePath: "dist/artifact"}})
	tests := []struct {
		name       string
		roots      discovery.Roots
		filesystem fstest.MapFS
	}{
		{name: "empty", roots: discovery.Roots{Source: "source"}},
		{name: "traversal", roots: discovery.Roots{Home: "../home", Source: "source"}},
		{name: "invalid UTF-8", roots: discovery.Roots{Home: domain.ArtifactPath(string([]byte{0xff})), Source: "source"}},
		{name: "escape", roots: validRoots(), filesystem: fstest.MapFS{"home/artifact": symlink("../../escape")}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := discovery.Discover(model, tt.filesystem, tt.roots)
			if err == nil {
				t.Fatal("expected error")
			}
		})
	}
}

func TestDiscoverAllowsSourceInsideHome(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{{HomePath: ".claude/CLAUDE.md", SourcePath: "dist/CLAUDE.md"}})
	filesystem := fstest.MapFS{
		"users/main/.claude/CLAUDE.md":                 symlink("../projects/mainframe/dist/CLAUDE.md"),
		"users/main/projects/mainframe/dist/CLAUDE.md": file(),
	}

	got, err := discovery.Discover(model, filesystem, discovery.Roots{
		Home: "users/main", Source: "users/main/projects/mainframe",
	})
	if err != nil {
		t.Fatalf("discover: %v", err)
	}
	want := observed("component", []domain.Artifact{{Path: ".claude/CLAUDE.md", Ownership: domain.OwnershipManagedExact}})
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("observed = %#v, want %#v", got, want)
	}
}

func TestDiscoverReturnsContextualFilesystemErrors(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{{HomePath: "artifact", SourcePath: "dist/artifact"}})
	tests := []struct {
		name    string
		fsys    *faultFS
		message string
	}{
		{name: "lstat", fsys: &faultFS{MapFS: fstest.MapFS{}, lstatErr: errors.New("denied")}, message: "inspect artifact"},
		{name: "readlink", fsys: &faultFS{MapFS: fstest.MapFS{"home/artifact": symlink("/source/dist/artifact")}, readlinkErr: errors.New("denied")}, message: "read link"},
		{name: "target stat", fsys: &faultFS{MapFS: fstest.MapFS{"home/artifact": symlink("/source/dist/artifact")}, statErr: errors.New("denied")}, message: "inspect link target"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := discovery.Discover(model, tt.fsys, validRoots())
			if err == nil || !strings.Contains(err.Error(), tt.message) {
				t.Fatalf("expected %q error, got %v", tt.message, err)
			}
		})
	}
}

func TestDiscoverRejectsNilFilesystem(t *testing.T) {
	model := testModel(t, []installmodel.ArtifactSpec{{HomePath: "artifact", SourcePath: "dist/artifact"}})
	_, err := discovery.Discover(model, nil, validRoots())
	if err == nil || !strings.Contains(err.Error(), "filesystem") {
		t.Fatalf("expected filesystem error, got %v", err)
	}
}

type faultFS struct {
	fstest.MapFS
	lstatErr, readlinkErr, statErr error
}

func (filesystem *faultFS) Lstat(name string) (fs.FileInfo, error) {
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

func testModel(t *testing.T, artifacts []installmodel.ArtifactSpec) installmodel.Model {
	t.Helper()
	model, err := installmodel.New([]installmodel.ComponentSpec{{ID: "component", Artifacts: artifacts}})
	if err != nil {
		t.Fatalf("new model: %v", err)
	}
	return model
}

func validRoots() discovery.Roots {
	return discovery.Roots{Home: "home", Source: "source"}
}

func symlink(target string) *fstest.MapFile {
	return &fstest.MapFile{Mode: fs.ModeSymlink, Data: []byte(target)}
}

func file() *fstest.MapFile {
	return &fstest.MapFile{Data: []byte("data")}
}

func observed(id domain.ComponentID, artifacts []domain.Artifact) domain.ObservedState {
	return domain.ObservedState{Components: []domain.ObservedComponent{{ID: id, Artifacts: artifacts}}}
}
