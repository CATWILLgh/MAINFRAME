//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestReleaseCommandsImportSwitchAndRollBackWithoutAdapterChanges(
	t *testing.T,
) {
	home := releaseCommandHome(t)
	firstSource := writeLocalReleaseFixture(t, "release-a", "binary-a\n")
	secondSource := writeLocalReleaseFixture(t, "release-b", "binary-b\n")

	first := reviewLocalRelease(t, firstSource)
	if !first.Applicable ||
		len(first.Operations) != 1 ||
		first.Operations[0].Kind != domain.OperationInstall ||
		first.ExpectedReview == "" {
		t.Fatalf("first review = %#v", first)
	}
	assertReleaseReviewReadOnly(t, home)
	applyReviewedRelease(t, first)
	assertActiveRelease(t, home, first.Target)

	second := reviewLocalRelease(t, secondSource)
	if second.Previous == nil ||
		*second.Previous != first.Target ||
		len(second.Operations) != 1 ||
		second.Operations[0].Kind != domain.OperationReplace {
		t.Fatalf("second review = %#v", second)
	}
	applyReviewedRelease(t, second)
	assertActiveRelease(t, home, second.Target)

	rollback := reviewCachedRelease(t, first.Target)
	if rollback.Previous == nil ||
		*rollback.Previous != second.Target ||
		!rollback.Applicable {
		t.Fatalf("rollback review = %#v", rollback)
	}
	applyReviewedRelease(t, rollback)
	assertActiveRelease(t, home, first.Target)

	noChange := reviewCachedRelease(t, first.Target)
	if noChange.Applicable ||
		noChange.ExpectedReview != "" ||
		noChange.ApplyRequest != nil ||
		len(noChange.Operations) != 0 {
		t.Fatalf("no-op review = %#v", noChange)
	}
	assertNoAdapterRoots(t, home)
}

func TestReleaseApplyRejectsLauncherDriftAfterReview(t *testing.T) {
	home := releaseCommandHome(t)
	first := reviewLocalRelease(
		t,
		writeLocalReleaseFixture(t, "release-a", "binary-a\n"),
	)
	applyReviewedRelease(t, first)
	second := reviewLocalRelease(
		t,
		writeLocalReleaseFixture(t, "release-b", "binary-b\n"),
	)
	launcher := filepath.Join(home, ".local", "bin", "mainframe")
	if err := os.Remove(launcher); err != nil {
		t.Fatalf("remove reviewed launcher: %v", err)
	}
	if err := os.WriteFile(launcher, []byte("foreign\n"), 0o700); err != nil {
		t.Fatalf("write foreign launcher: %v", err)
	}

	exitCode, _, stderr := applyReleaseForTest(t, second)
	if exitCode == 0 || !strings.Contains(stderr, "review again") {
		t.Fatalf("stale apply exit = %d, stderr = %q", exitCode, stderr)
	}
	content, err := os.ReadFile(launcher)
	if err != nil || string(content) != "foreign\n" {
		t.Fatalf("stale apply changed foreign launcher: %q, %v", content, err)
	}
}

func TestReleaseReviewRejectsLauncherPointingToUnpublishedCachePath(
	t *testing.T,
) {
	home := releaseCommandHome(t)
	source := writeLocalReleaseFixture(t, "release-a", "binary-a\n")
	initial := reviewLocalRelease(t, source)
	target := filepath.Join(
		home,
		".local",
		"share",
		"mainframe",
		"releases",
		initial.Target.ID,
		initial.Target.IndexSHA256,
		"bin",
		"mainframe",
	)
	launcher := filepath.Join(home, ".local", "bin", "mainframe")
	if err := os.MkdirAll(filepath.Dir(launcher), 0o700); err != nil {
		t.Fatalf("create launcher parent: %v", err)
	}
	if err := os.Symlink(target, launcher); err != nil {
		t.Fatalf("create dangling launcher: %v", err)
	}

	review := reviewLocalRelease(t, source)
	if review.Applicable ||
		review.ApplyRequest != nil ||
		!containsReleaseNotice(review.Notices, releasePredictedTargetNotice) {
		t.Fatalf("dangling target review = %#v", review)
	}
	if _, err := os.Lstat(
		filepath.Join(home, ".local", "share", "mainframe"),
	); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("review imported release behind dangling launcher: %v", err)
	}
}

func containsReleaseNotice(notices []string, expected string) bool {
	for _, notice := range notices {
		if notice == expected {
			return true
		}
	}
	return false
}

func releaseCommandHome(t *testing.T) string {
	t.Helper()
	home := canonicalTempDir(t)
	t.Cleanup(func() {
		_ = filepath.WalkDir(
			home,
			func(path string, entry os.DirEntry, err error) error {
				if err == nil && entry.IsDir() {
					_ = os.Chmod(path, 0o700)
				}
				return nil
			},
		)
	})
	t.Setenv("HOME", home)
	t.Setenv("XDG_DATA_HOME", filepath.Join(home, ".local", "share"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(home, ".local", "state"))
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(home, ".config"))
	t.Setenv("CODEX_HOME", filepath.Join(home, ".codex"))
	t.Setenv(releaseRootEnvironment, "")
	return home
}

func reviewLocalRelease(
	t *testing.T,
	source string,
) releaseReviewResponse {
	t.Helper()
	request := releaseChangeRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseChangeKind,
		Operation:     releaseOperationImport,
		SourcePath:    source,
	}
	return runReleaseReviewForTest(t, request)
}

func reviewCachedRelease(
	t *testing.T,
	identity executor.ReleaseIdentity,
) releaseReviewResponse {
	t.Helper()
	request := releaseChangeRequest{
		SchemaVersion: releaseProtocolVersion,
		Kind:          releaseChangeKind,
		Operation:     releaseOperationActivate,
		ReleaseID:     identity.ID,
		IndexSHA256:   identity.IndexSHA256,
	}
	return runReleaseReviewForTest(t, request)
}

func runReleaseReviewForTest(
	t *testing.T,
	request releaseChangeRequest,
) releaseReviewResponse {
	t.Helper()
	payload, err := json.Marshal(request)
	if err != nil {
		t.Fatalf("encode release review request: %v", err)
	}
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{"release", "review"},
		bytes.NewReader(payload),
		&stdout,
		&stderr,
	)
	if exitCode != 0 {
		t.Fatalf("release review exit = %d, stderr = %q", exitCode, stderr.String())
	}
	var response releaseReviewResponse
	if err := json.Unmarshal(stdout.Bytes(), &response); err != nil {
		t.Fatalf("decode release review: %v; output = %q", err, stdout.String())
	}
	return response
}

func applyReviewedRelease(t *testing.T, review releaseReviewResponse) {
	t.Helper()
	exitCode, stdout, stderr := applyReleaseForTest(t, review)
	if exitCode != 0 {
		t.Fatalf("release apply exit = %d, stderr = %q", exitCode, stderr)
	}
	var response releaseApplyResponse
	if err := json.Unmarshal([]byte(stdout), &response); err != nil {
		t.Fatalf("decode release apply: %v; output = %q", err, stdout)
	}
	if !response.Applied || response.Active == "" {
		t.Fatalf("release apply response = %#v", response)
	}
}

func applyReleaseForTest(
	t *testing.T,
	review releaseReviewResponse,
) (int, string, string) {
	t.Helper()
	payload, err := json.Marshal(review.ApplyRequest)
	if err != nil {
		t.Fatalf("encode release apply request: %v", err)
	}
	var stdout, stderr bytes.Buffer
	exitCode := run(
		[]string{
			"release", "apply", "--confirm", review.ExpectedReview,
		},
		bytes.NewReader(payload),
		&stdout,
		&stderr,
	)
	return exitCode, stdout.String(), stderr.String()
}

func assertReleaseReviewReadOnly(t *testing.T, home string) {
	t.Helper()
	for _, path := range []string{
		filepath.Join(home, ".local", "share", "mainframe"),
		filepath.Join(home, ".local", "bin"),
		filepath.Join(home, ".local", "state", "mainframe"),
	} {
		if _, err := os.Lstat(path); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("release review created %q: %v", path, err)
		}
	}
}

func assertActiveRelease(
	t *testing.T,
	home string,
	identity executor.ReleaseIdentity,
) {
	t.Helper()
	launcher := filepath.Join(home, ".local", "bin", "mainframe")
	target, err := os.Readlink(launcher)
	if err != nil {
		t.Fatalf("read active launcher: %v", err)
	}
	expected := filepath.Join(
		home,
		".local",
		"share",
		"mainframe",
		"releases",
		identity.ID,
		identity.IndexSHA256,
		"bin",
		"mainframe",
	)
	if target != expected {
		t.Fatalf("active launcher = %q, want %q", target, expected)
	}
}

func assertNoAdapterRoots(t *testing.T, home string) {
	t.Helper()
	for _, relative := range []string{
		".claude",
		".codex",
		".config/opencode",
		".gemini",
	} {
		path := filepath.Join(home, relative)
		if _, err := os.Lstat(path); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("release lifecycle created adapter root %q: %v", path, err)
		}
	}
}

func writeLocalReleaseFixture(
	t *testing.T,
	releaseID, launcher string,
) string {
	t.Helper()
	root := t.TempDir()
	binary := filepath.Join(root, "bin", "mainframe")
	writeFixtureFile(t, binary, []byte(launcher), 0o555)
	manifest := filepath.Join(root, "bin", "bundle.json")
	writeFixtureJSON(t, manifest, map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-bundle",
		"component":      "mainframe-cli",
		"dependencies":   []string{},
		"install_units": []any{map[string]any{
			"id": "mainframe-cli.binary", "kind": "file", "source": "mainframe",
			"target": map[string]any{"root": "user-bin", "path": "mainframe"},
		}},
		"legacy_artifacts": []any{},
		"resources":        []any{},
		"payload_files": []any{map[string]any{
			"path": "mainframe", "mode": "0555",
			"size": len(launcher), "sha256": fixtureDigest(t, binary),
		}},
		"runtime_profile": map[string]string{},
		"mcp_projections": []any{},
	}, 0o644)
	catalog := writePlanCatalog(t, root)
	writeFixtureJSON(t, filepath.Join(root, "release.json"), map[string]any{
		"schema_version": 2,
		"kind":           "mainframe-release",
		"release_id":     releaseID,
		"mcp_catalog": map[string]any{
			"path": "metadata/mcp-catalog.json", "sha256": fixtureDigest(t, catalog),
		},
		"manifests": []any{map[string]any{
			"component": "mainframe-cli",
			"path":      "bin/bundle.json",
			"sha256":    fixtureDigest(t, manifest),
		}},
	}, 0o644)
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil || entry.IsDir() {
			return err
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		return os.Chmod(path, info.Mode().Perm()&^0o222)
	})
	if err != nil {
		t.Fatalf("seal local release fixture: %v", err)
	}
	return root
}
