package secretstore

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGetReadsLegacyStoreWithoutCreatingSidecars(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "credentials")
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(dir, storeName),
		[]byte("API_KEY=legacy\n"),
		0o400,
	); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(filepath.Join(dir, storeName), 0o400); err != nil {
		t.Fatal(err)
	}

	value, err := New(dir).Get("API_KEY")
	if err != nil || value != "legacy" {
		t.Fatalf("get legacy value = %q, %v", value, err)
	}
	info, err := os.Stat(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got := info.Mode().Perm(); got != 0o755 {
		t.Fatalf("directory permissions = %o, want unchanged 755", got)
	}
	for _, name := range []string{backupName, generationName, lockName} {
		if _, err := os.Lstat(filepath.Join(dir, name)); !os.IsNotExist(err) {
			t.Fatalf("read created %s: %v", name, err)
		}
	}
}

func TestMutationRepairsLegacyCredentialDirectoryPermissions(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "credentials")
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o755); err != nil {
		t.Fatal(err)
	}

	if err := New(dir).Set("API_KEY", "value"); err != nil {
		t.Fatalf("set: %v", err)
	}
	info, err := os.Stat(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got := info.Mode().Perm(); got != 0o700 {
		t.Fatalf("directory permissions = %o, want 700", got)
	}
}

func TestMutationPreservesLegacyCommentsAndBlankLines(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := os.MkdirAll(store.dir, 0o700); err != nil {
		t.Fatal(err)
	}
	legacy := "# personal credentials\n\nAPI_KEY='old value'\n"
	if err := os.WriteFile(store.Path(), []byte(legacy), 0o600); err != nil {
		t.Fatal(err)
	}

	if err := store.Set("OTHER_KEY", "other value"); err != nil {
		t.Fatalf("set against legacy comments: %v", err)
	}
	content, err := os.ReadFile(store.Path())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(content), "# personal credentials\n\n") {
		t.Fatalf("comments or blank lines were discarded: %q", content)
	}
}

func TestSafeLegacyAssignmentFormsAreMigratedToCanonicalForm(t *testing.T) {
	store := New(filepath.Join(t.TempDir(), "credentials"))
	if err := os.MkdirAll(store.dir, 0o700); err != nil {
		t.Fatal(err)
	}
	legacy := "BARE=value-1\nDOUBLE=\"value 2\"\n"
	if err := os.WriteFile(store.Path(), []byte(legacy), 0o600); err != nil {
		t.Fatal(err)
	}

	bare, bareErr := store.Get("BARE")
	double, doubleErr := store.Get("DOUBLE")
	if bareErr != nil || doubleErr != nil ||
		bare != "value-1" || double != "value 2" {
		t.Fatalf(
			"legacy values = %q/%v, %q/%v",
			bare,
			bareErr,
			double,
			doubleErr,
		)
	}
	if err := store.Set("OTHER", "third"); err != nil {
		t.Fatal(err)
	}
	assertPrivateCanonicalFile(
		t,
		store.Path(),
		"BARE='value-1'\nDOUBLE='value 2'\nOTHER='third'\n",
	)
}
