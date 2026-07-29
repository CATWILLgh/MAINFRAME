//go:build darwin || linux

package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestCompleteLegacyReviewReturnsBulkApplyCommitment(t *testing.T) {
	fixture := newLegacyApplyFixture(t)
	var draft map[string]any
	_ = json.Unmarshal(legacyReviewPayload(true, false), &draft)
	reverseAnySlice(draft["new_instances"].([]any))
	reverseAnySlice(draft["choices"].([]any))
	payload, _ := json.Marshal(draft)
	review := fixture.review(payload)

	assertNoCanary(t, review.raw, fixture.stateRoot)
	if !review.ApplyAvailable {
		t.Fatalf("complete legacy review apply_available = false")
	}
	if len(review.Changes) != 2 ||
		len(review.ApplyRequest) == 0 ||
		!strings.HasPrefix(review.ExpectedReview, "sha256:") {
		t.Fatalf("legacy review contract = %#v", review)
	}
	var request map[string]any
	if err := json.Unmarshal(review.ApplyRequest, &request); err != nil {
		t.Fatalf("decode normalized apply request: %v", err)
	}
	instances, ok := request["instances"].([]any)
	choices := request["choices"].([]any)
	if request["kind"] != "mainframe-legacy-credential-transfer-apply" ||
		!ok || len(instances) != 2 ||
		instances[0].(map[string]any)["id"] != "context7-home" ||
		choices[0].(map[string]any)["proposal"].(map[string]any)["reference_name"] !=
			"LEGACY_ALPHA" {
		t.Fatalf("normalized apply request = %#v", request)
	}
}

func reverseAnySlice(values []any) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}

func TestLegacyApplyPublishesWholeCatalogWithoutTouchingSources(t *testing.T) {
	fixture := newLegacyApplyFixture(t)
	before := snapshotLegacySource(t, fixture.sourcePath)
	review := fixture.completeReview()
	exit, stdout, stderr := fixture.apply(review, review.ExpectedReview)
	if exit != 0 {
		t.Fatalf("legacy apply exit = %d, stderr = %q", exit, stderr)
	}
	after := snapshotLegacySource(t, fixture.sourcePath)
	if !bytes.Equal(before.content, after.content) ||
		before.mode != after.mode ||
		before.device != after.device ||
		before.inode != after.inode ||
		before.birth != after.birth {
		t.Fatalf("legacy source identity changed: before=%#v after=%#v", before, after)
	}
	assertAppliedCatalog(t, fixture.catalogPath)
	assertNoCanary(t, stdout, stderr, fixture.stateRoot, fixture.catalogPath)
	baseline := snapshotLegacySource(t, fixture.catalogPath)
	exit, _, _ = fixture.apply(review, review.ExpectedReview)
	current := snapshotLegacySource(t, fixture.catalogPath)
	if exit == 0 || !reflect.DeepEqual(baseline, current) {
		t.Fatal("repeated legacy apply republished the desired catalog")
	}
}

func TestPartialLegacyContentCanApplyRecognizedReferences(t *testing.T) {
	fixture := newLegacyApplyFixture(t)
	partial := strings.Replace(
		legacySourceContent(),
		"## Home\n",
		"## Home\nPurpose: requires manual review\n",
		1,
	)
	writeFixtureFile(t, fixture.sourcePath, []byte(partial), 0o600)
	before := snapshotLegacySource(t, fixture.sourcePath)
	review := fixture.completeReview()
	if !review.ApplyAvailable ||
		!review.ManualContentReviewRequired ||
		review.RetirementReady {
		t.Fatalf("partial-content review = %#v", review)
	}
	exit, stdout, stderr := fixture.apply(review, review.ExpectedReview)
	if exit != 0 {
		t.Fatalf("partial-content apply exit = %d, stderr = %q", exit, stderr)
	}
	after := snapshotLegacySource(t, fixture.sourcePath)
	if !reflect.DeepEqual(before, after) {
		t.Fatal("partial-content apply changed the legacy source")
	}
	assertAppliedCatalog(t, fixture.catalogPath)
	assertNoCanary(t, stdout, stderr, fixture.stateRoot, fixture.catalogPath)
}

func TestLegacyApplyIsReviewedCLIOnlyAndDoesNotEnableTUIApply(t *testing.T) {
	var apply, tui *commandSpec
	for index := range registeredCommands {
		switch registeredCommands[index].ID {
		case "credentials.legacy-apply":
			apply = &registeredCommands[index]
		case "tui.open":
			tui = &registeredCommands[index]
		}
	}
	if apply == nil ||
		apply.Usage != "mainframe credentials legacy-apply --confirm <digest>" ||
		apply.Effect != effectReviewedWrite ||
		apply.Confirmation != confirmationDigest {
		t.Fatalf("legacy apply command = %#v", apply)
	}
	if tui == nil || tui.Confirmation != confirmationTerminal {
		t.Fatalf("TUI apply contract changed = %#v", tui)
	}
}

func TestLegacyApplyRejectsStaleOrForgedReviewWithoutWriting(t *testing.T) {
	tests := map[string]func(*testing.T, legacyApplyFixture, legacyApplyReview) string{
		"catalog": func(t *testing.T, fixture legacyApplyFixture, _ legacyApplyReview) string {
			executeCredentialChange(t, context7HomeCreateRequest)
			return ""
		},
		"source content": func(t *testing.T, fixture legacyApplyFixture, _ legacyApplyReview) string {
			writeFixtureFile(t, fixture.sourcePath, []byte(legacySourceContent()+"\n"), 0o600)
			return ""
		},
		"source identity": func(t *testing.T, fixture legacyApplyFixture, _ legacyApplyReview) string {
			replacement := filepath.Join(filepath.Dir(fixture.sourcePath), "replacement")
			writeFixtureFile(t, replacement, []byte(legacySourceContent()), 0o600)
			if err := os.Rename(replacement, fixture.sourcePath); err != nil {
				t.Fatalf("replace legacy source: %v", err)
			}
			return ""
		},
		"forged digest": func(_ *testing.T, _ legacyApplyFixture, _ legacyApplyReview) string {
			return "sha256:" + strings.Repeat("f", 64)
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			fixture := newLegacyApplyFixture(t)
			review := fixture.completeReview()
			digest := mutate(t, fixture, review)
			if digest == "" {
				digest = review.ExpectedReview
			}
			before, _ := os.ReadFile(fixture.catalogPath)
			exit, stdout, stderr := fixture.apply(review, digest)
			after, _ := os.ReadFile(fixture.catalogPath)
			if exit == 0 || !bytes.Equal(before, after) {
				t.Fatalf("rejected apply exit = %d changed catalog", exit)
			}
			assertNoCanary(t, stdout, stderr, fixture.stateRoot)
		})
	}
}

func TestIncompleteBlockedAndNoChangeLegacyReviewsDoNotWrite(t *testing.T) {
	t.Run("pending choices", func(t *testing.T) {
		fixture := newLegacyApplyFixture(t)
		payload := legacyReviewPayload(true, false)
		var request map[string]any
		_ = json.Unmarshal(payload, &request)
		request["choices"] = request["choices"].([]any)[:1]
		request["new_instances"] = request["new_instances"].([]any)[:1]
		encoded, _ := json.Marshal(request)
		review := fixture.review(encoded)
		assertReviewCannotApply(t, fixture, review)
	})
	t.Run("blocked source", func(t *testing.T) {
		fixture := newLegacyApplyFixture(t)
		if err := os.Chmod(fixture.sourcePath, 0o644); err != nil {
			t.Fatalf("make source unsafe: %v", err)
		}
		exit, stdout, stderr := runCredentialCommand(
			[]string{"credentials", "legacy-review"}, legacyReviewPayload(true, false),
		)
		if exit == 0 || len(stdout) != 0 {
			t.Fatalf("blocked review exit/stdout/stderr = %d/%q/%q", exit, stdout, stderr)
		}
		assertCatalogMissing(t, fixture.catalogPath)
	})
	t.Run("skip only", func(t *testing.T) {
		fixture := newLegacyApplyFixture(t)
		assertReviewCannotApply(t, fixture, fixture.review(legacyReviewPayload(false, false)))
	})
	t.Run("zero changes", func(t *testing.T) {
		fixture := newLegacyApplyFixture(t)
		writeExistingLegacyCatalog(t, fixture.catalogPath)
		before, _ := os.ReadFile(fixture.catalogPath)
		review := fixture.review(legacyReviewPayload(true, true))
		if review.ApplyAvailable || len(review.ApplyRequest) != 0 ||
			len(review.ExpectedReview) != 0 {
			t.Fatalf("zero-change review is applicable: %#v", review)
		}
		after, _ := os.ReadFile(fixture.catalogPath)
		if !bytes.Equal(before, after) {
			t.Fatal("zero-change review wrote the catalog")
		}
	})
}

func TestOrdinaryCredentialCommandsDoNotInspectLegacySources(t *testing.T) {
	fixture := newLegacyApplyFixture(t)
	if err := os.Remove(fixture.sourcePath); err != nil {
		t.Fatalf("remove legacy source: %v", err)
	}
	if err := os.Symlink("/does/not/exist", fixture.sourcePath); err != nil {
		t.Fatalf("create unsafe legacy source: %v", err)
	}
	review := reviewCredentialChange(t, context7HomeCreateRequest)
	exit, stdout, stderr := applyCredentialReview(t, review)
	if exit != 0 {
		t.Fatalf("ordinary apply exit = %d, stderr = %q", exit, stderr)
	}
	assertAppliedCatalogCount(t, fixture.catalogPath, 1)
	assertNoCanary(t, stdout, stderr, fixture.stateRoot, fixture.catalogPath)
}

func assertReviewCannotApply(
	t *testing.T,
	fixture legacyApplyFixture,
	review legacyApplyReview,
) {
	t.Helper()
	if review.ApplyAvailable || len(review.ApplyRequest) != 0 ||
		len(review.ExpectedReview) != 0 {
		t.Fatalf("non-applicable review = %#v", review)
	}
	assertCatalogMissing(t, fixture.catalogPath)
}

func assertAppliedCatalog(t *testing.T, path string) {
	t.Helper()
	assertAppliedCatalogCount(t, path, 2)
	info, err := os.Stat(path)
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("catalog stat = %#v, %v", info, err)
	}
}

func assertAppliedCatalogCount(t *testing.T, path string, want int) {
	t.Helper()
	catalog := readJSONMap(t, path)
	instances, ok := catalog["instances"].([]any)
	if catalog["kind"] != "mainframe-credential-instances" ||
		!ok || len(instances) != want {
		t.Fatalf("applied catalog = %#v", catalog)
	}
}

func assertCatalogMissing(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("credential catalog exists: %v", err)
	}
}

func writeExistingLegacyCatalog(t *testing.T, path string) {
	t.Helper()
	writeFixtureJSON(t, path, map[string]any{
		"schema_version": 1, "kind": "mainframe-credential-instances",
		"instances": []any{
			legacyInstance("context7-home", "Home", "LEGACY_ALPHA"),
			legacyInstance("context7-work", "Work", "LEGACY_BETA"),
		},
	}, 0o600)
}

func assertNoCanary(t *testing.T, outputs ...string) {
	t.Helper()
	for _, output := range outputs {
		if strings.Contains(output, legacySecretValueCanary) {
			t.Fatalf("secret value canary exposed in %q", output)
		}
		info, err := os.Stat(output)
		if err != nil {
			continue
		}
		if !info.IsDir() {
			payload, _ := os.ReadFile(output)
			if bytes.Contains(payload, []byte(legacySecretValueCanary)) {
				t.Fatalf("secret value canary stored in %q", output)
			}
			continue
		}
		_ = filepath.WalkDir(output, func(path string, entry fs.DirEntry, err error) error {
			if err == nil && !entry.IsDir() {
				payload, _ := os.ReadFile(path)
				if bytes.Contains(payload, []byte(legacySecretValueCanary)) {
					t.Fatalf("secret value canary stored in %q", path)
				}
			}
			return nil
		})
	}
}
