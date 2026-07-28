//go:build darwin || linux

package main

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func TestReleaseApplyWithWrongConfirmationDoesNotImport(t *testing.T) {
	home := releaseCommandHome(t)
	review := reviewLocalRelease(
		t,
		writeLocalReleaseFixture(t, "release-a", "binary-a\n"),
	)
	review.ExpectedReview = "sha256:" + strings.Repeat("0", 64)

	exitCode, _, stderr := applyReleaseForTest(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "review again") {
		t.Fatalf("wrong confirmation exit = %d, stderr = %q", exitCode, stderr)
	}
	assertReleaseNotCached(t, home, review.Target)
}

func TestReleaseApplyDoesNotRecoverBeforeConfirmation(t *testing.T) {
	home := releaseCommandHome(t)
	review := reviewLocalRelease(
		t,
		writeLocalReleaseFixture(t, "release-a", "binary-a\n"),
	)
	stateRoot := filepath.Join(home, ".local", "state", "mainframe")
	saveEmptyProductionJournal(t, stateRoot)

	exitCode, _, stderr := applyReleaseForTest(t, review)
	if exitCode == 0 || !strings.Contains(stderr, "review again") {
		t.Fatalf("pending journal exit = %d, stderr = %q", exitCode, stderr)
	}
	journal, err := executor.ReadUnixJournal(stateRoot)
	if err != nil || journal == nil {
		t.Fatalf("pending journal was recovered = %#v, %v", journal, err)
	}
	assertReleaseNotCached(t, home, review.Target)
}

func assertReleaseNotCached(
	t *testing.T,
	home string,
	identity executor.ReleaseIdentity,
) {
	t.Helper()
	path := filepath.Join(
		home,
		".local",
		"share",
		"mainframe",
		"releases",
		identity.ID,
		identity.IndexSHA256,
	)
	if _, err := os.Lstat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("release cache path exists after rejected apply: %v", err)
	}
}
