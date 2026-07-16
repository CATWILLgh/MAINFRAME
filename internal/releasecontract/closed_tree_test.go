package releasecontract_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLoadRejectsUnindexedReleaseTreeEntries(t *testing.T) {
	tests := []struct {
		name   string
		create func(*testing.T, string)
	}{
		{
			name: "top-level file",
			create: func(t *testing.T, root string) {
				writeFile(t, filepath.Join(root, "notes.txt"), "unindexed\n", 0o644)
			},
		},
		{
			name: "top-level empty directory",
			create: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "unindexed"))
			},
		},
		{
			name: "nested file outside indexed bundle",
			create: func(t *testing.T, root string) {
				directory := filepath.Join(root, "unindexed", "nested")
				mkdir(t, directory)
				writeFile(t, filepath.Join(directory, "extra.txt"), "unindexed\n", 0o644)
			},
		},
		{
			name: "nested empty directory outside indexed bundle",
			create: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "unindexed", "nested", "empty"))
			},
		},
		{
			name: "nested file inside indexed bundle",
			create: func(t *testing.T, root string) {
				directory := filepath.Join(root, "bundles", "codex", "nested")
				mkdir(t, directory)
				writeFile(t, filepath.Join(directory, "extra.txt"), "unindexed\n", 0o644)
			},
		},
		{
			name: "nested empty directory inside indexed bundle",
			create: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "bundles", "codex", "empty"))
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := writeFixture(t)
			test.create(t, root)

			if _, err := releasecontract.Load(root); err == nil {
				t.Fatal("release with unindexed tree entry was accepted")
			}
		})
	}
}

func mkdir(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(path, 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", path, err)
	}
}
