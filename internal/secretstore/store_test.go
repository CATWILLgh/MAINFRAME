package secretstore

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestStoreCRUDUsesCanonicalPrivateFiles(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))

	if err := store.Create("FIRST_KEY", strings.NewReader("first value")); err != nil {
		t.Fatalf("create: %v", err)
	}
	if err := store.Set("SECOND_KEY", "quote ' value"); err != nil {
		t.Fatalf("set: %v", err)
	}
	if err := store.Set("FIRST_KEY", "replacement"); err != nil {
		t.Fatalf("replace: %v", err)
	}

	value, err := store.Get("FIRST_KEY")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if value != "replacement" {
		t.Fatalf("get = %q", value)
	}
	names, err := store.List()
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if !reflect.DeepEqual(names, []string{"FIRST_KEY", "SECOND_KEY"}) {
		t.Fatalf("list = %#v", names)
	}

	if err := store.Delete("SECOND_KEY"); err != nil {
		t.Fatalf("delete: %v", err)
	}
	assertPrivateCanonicalFile(t, store.Path(), "FIRST_KEY='replacement'\n")
	assertPrivateCanonicalFile(t, store.BackupPath(), "FIRST_KEY='replacement'\n")
}

func TestCreateRejectsReplacementAndInvalidInputWithoutLeakingValue(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("API_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	for _, input := range []string{"", "new\nvalue", "new\rvalue", "new\x00value"} {
		err := store.Create("API_KEY", strings.NewReader(input))
		if err == nil {
			t.Fatalf("Create(%q) succeeded", input)
		}
		if input != "" && strings.Contains(err.Error(), input) ||
			strings.Contains(err.Error(), "old value") {
			t.Fatalf("error leaked a value: %v", err)
		}
	}
	value, err := store.Get("API_KEY")
	if err != nil || value != "old value" {
		t.Fatalf("unchanged value = %q, %v", value, err)
	}
}

func TestQuoteHeavyValueAtLimitRemainsReadable(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	value := strings.Repeat("'", maxValueBytes)
	if err := store.Set("API_KEY", value); err != nil {
		t.Fatalf("set: %v", err)
	}
	got, err := store.Get("API_KEY")
	if err != nil || got != value {
		t.Fatalf("get length/error = %d/%v", len(got), err)
	}
}

func TestPreparedRetirementRejectsEveryInterveningMutation(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("OLD_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	generation, err := store.PrepareRetire("OLD_KEY")
	if err != nil {
		t.Fatal(err)
	}
	if generation == "" || strings.Contains(generation, "old value") {
		t.Fatalf("unsafe generation %q", generation)
	}

	if err := store.Set("OTHER_KEY", "other value"); err != nil {
		t.Fatal(err)
	}
	if err := store.DeleteIfGeneration("OLD_KEY", generation); !errors.Is(err, ErrGenerationChanged) {
		t.Fatalf("stale delete error = %v", err)
	}
	if value, err := store.Get("OLD_KEY"); err != nil || value != "old value" {
		t.Fatalf("old key changed: %q, %v", value, err)
	}

	fresh, err := store.PrepareRetire("OLD_KEY")
	if err != nil {
		t.Fatal(err)
	}
	if err := store.DeleteIfGeneration("OLD_KEY", fresh); err != nil {
		t.Fatalf("fresh delete: %v", err)
	}
	if _, err := store.Get("OLD_KEY"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("deleted get error = %v", err)
	}
}

func TestPrepareRetireRejectsMalformedGeneration(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("OLD_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(store.dir, generationName),
		[]byte(strings.Repeat("x", 64)+"\n"),
		0o600,
	); err != nil {
		t.Fatal(err)
	}

	if _, err := store.PrepareRetire("OLD_KEY"); !errors.Is(err, ErrUnsafeStore) {
		t.Fatalf("prepare error = %v", err)
	}
}

func TestReplacementAndDeletionSanitizeBackup(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("API_KEY", "retired value"); err != nil {
		t.Fatal(err)
	}
	if err := store.Set("API_KEY", "current value"); err != nil {
		t.Fatal(err)
	}
	assertFileExcludes(t, store.Path(), "retired value")
	assertFileExcludes(t, store.BackupPath(), "retired value")

	if err := store.Delete("API_KEY"); err != nil {
		t.Fatal(err)
	}
	assertFileExcludes(t, store.Path(), "current value")
	assertFileExcludes(t, store.BackupPath(), "current value")
}

func TestFailureBeforePrimaryPublicationLeavesGenerationInvalidated(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "credentials")
	store := New(dir)
	if err := store.Set("API_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	generation, err := store.PrepareRetire("API_KEY")
	if err != nil {
		t.Fatal(err)
	}
	store.failure = func(point FailurePoint) error {
		if point == BeforePrimaryPublication {
			return errors.New("injected publication failure")
		}
		return nil
	}
	if err := store.Set("API_KEY", "new value"); err == nil {
		t.Fatal("set succeeded through injected failure")
	}

	reopened := New(dir)
	if err := reopened.DeleteIfGeneration("API_KEY", generation); !errors.Is(err, ErrGenerationChanged) {
		t.Fatalf("old generation remained valid: %v", err)
	}
	assertFileExcludes(t, reopened.BackupPath(), "old value")
}

func TestInterruptedPublicationKeepsAValidPrimaryAndInvalidatesPreparedDelete(
	t *testing.T,
) {
	for _, point := range []FailurePoint{
		BeforeBackupPublication,
		BeforePrimaryPublication,
	} {
		t.Run(string(point), func(t *testing.T) {
			dir := filepath.Join(t.TempDir(), "credentials")
			store := New(dir)
			if err := store.Set("API_KEY", "old value"); err != nil {
				t.Fatal(err)
			}
			generation, err := store.PrepareRetire("API_KEY")
			if err != nil {
				t.Fatal(err)
			}
			store.failure = func(current FailurePoint) error {
				if current == point {
					return errors.New("injected publication failure")
				}
				return nil
			}

			if err := store.Set("API_KEY", "new value"); err == nil {
				t.Fatal("set succeeded through injected failure")
			}
			reopened := New(dir)
			value, err := reopened.Get("API_KEY")
			if err != nil || value != "old value" {
				t.Fatalf("primary became invalid: %q, %v", value, err)
			}
			if err := reopened.DeleteIfGeneration(
				"API_KEY",
				generation,
			); !errors.Is(err, ErrGenerationChanged) {
				t.Fatalf("prepared delete remained valid: %v", err)
			}
		})
	}
}

func TestRejectsSymlinkAndNonPrivateStoreObjects(t *testing.T) {
	for _, target := range []string{"directory", "store", "backup", "generation", "lock"} {
		t.Run(target, func(t *testing.T) {
			root := t.TempDir()
			dir := filepath.Join(root, "credentials")
			external := filepath.Join(root, "external")
			if err := os.WriteFile(external, []byte("unchanged"), 0o600); err != nil {
				t.Fatal(err)
			}
			if target == "directory" {
				if err := os.Symlink(root, dir); err != nil {
					t.Fatal(err)
				}
			} else {
				if err := os.Mkdir(dir, 0o700); err != nil {
					t.Fatal(err)
				}
				name := map[string]string{
					"store": "secrets.env", "backup": "secrets.env.bak",
					"generation": ".generation", "lock": ".lock",
				}[target]
				if err := os.Symlink(external, filepath.Join(dir, name)); err != nil {
					t.Fatal(err)
				}
			}
			err := New(dir).Set("API_KEY", "new value")
			if !errors.Is(err, ErrUnsafeStore) {
				t.Fatalf("error = %v", err)
			}
			content, readErr := os.ReadFile(external)
			if readErr != nil || string(content) != "unchanged" {
				t.Fatalf("external changed: %q, %v", content, readErr)
			}
		})
	}
}

func TestEditUsesValidatedTemporaryFile(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("API_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	store.editor = func(path string) error {
		return os.WriteFile(path, []byte("API_KEY='new value'\nOTHER='second'\n"), 0o600)
	}
	if err := store.Edit(); err != nil {
		t.Fatalf("edit: %v", err)
	}
	assertPrivateCanonicalFile(t, store.Path(), "API_KEY='new value'\nOTHER='second'\n")

	store.editor = func(path string) error {
		return os.WriteFile(path, []byte("API_KEY=$(unsafe)\n"), 0o600)
	}
	if err := store.Edit(); err == nil {
		t.Fatal("malformed edit succeeded")
	}
	assertPrivateCanonicalFile(t, store.Path(), "API_KEY='new value'\nOTHER='second'\n")
}

func TestEditRejectsOversizedTemporaryFileWithoutTruncation(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := store.Set("API_KEY", "old value"); err != nil {
		t.Fatal(err)
	}
	store.editor = func(path string) error {
		prefix := "API_KEY='new value'\n"
		padding := "#" + strings.Repeat("x", maxStoreBytes-len(prefix)-2) + "\n"
		return os.WriteFile(path, []byte(prefix+padding+"TRAILING='discarded'\n"), 0o600)
	}

	if err := store.Edit(); !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("error = %v, want ErrInvalidInput", err)
	}
	assertPrivateCanonicalFile(t, store.Path(), "API_KEY='old value'\n")
}

func assertPrivateCanonicalFile(t *testing.T, path, want string) {
	t.Helper()
	info, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	if !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 {
		t.Fatalf("%s mode = %v", path, info.Mode())
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != want {
		t.Fatalf("%s = %q, want %q", path, content, want)
	}
}

func assertFileExcludes(t *testing.T, path, forbidden string) {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(content), forbidden) {
		t.Fatalf("%s retained retired value", path)
	}
}
