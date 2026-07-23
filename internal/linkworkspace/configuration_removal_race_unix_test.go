//go:build darwin || linux

package linkworkspace

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestConfigurationRemovalRestoresUnexpectedMovedSource(t *testing.T) {
	tests := map[string]func(*testing.T, string, string){
		"regular file": func(t *testing.T, public, _ string) {
			t.Helper()
			if err := os.WriteFile(public, []byte("foreign"), 0o600); err != nil {
				t.Fatal(err)
			}
		},
		"symlink": func(t *testing.T, public, parent string) {
			t.Helper()
			target := filepath.Join(parent, "foreign-target")
			if err := os.WriteFile(target, []byte("foreign"), 0o600); err != nil {
				t.Fatal(err)
			}
			if err := os.Symlink(target, public); err != nil {
				t.Fatal(err)
			}
		},
		"hardlink": func(t *testing.T, public, parent string) {
			t.Helper()
			target := filepath.Join(parent, "foreign-hardlink")
			if err := os.WriteFile(target, []byte("foreign"), 0o600); err != nil {
				t.Fatal(err)
			}
			if err := os.Link(target, public); err != nil {
				t.Fatal(err)
			}
		},
		"directory": func(t *testing.T, public, _ string) {
			t.Helper()
			if err := os.Mkdir(public, 0o700); err != nil {
				t.Fatal(err)
			}
		},
	}
	for name, create := range tests {
		t.Run(name, func(t *testing.T) {
			fixture := newConfigurationFixture(
				t,
				"settings.json",
				[]byte("before"),
				0o600,
			)
			mutation := fixture.preparedRemovalMutation(t)
			fixture.prepareRemoval(t, &mutation)
			if err := os.Remove(fixture.publicPath()); err != nil {
				t.Fatal(err)
			}
			create(t, fixture.publicPath(), fixture.target)
			privatePath := filepath.Join(
				fixture.target,
				mutation.Private.Name,
				mutation.StagedName,
			)
			if err := os.Rename(fixture.publicPath(), privatePath); err != nil {
				t.Fatal(err)
			}
			context, err := fixture.workspace.openConfigurationMutation(mutation)
			if err != nil {
				t.Fatal(err)
			}
			defer context.close()

			if _, err := inferConfigurationPublication(
				context,
				mutation,
				errors.New("injected rename uncertainty"),
			); err == nil {
				t.Fatal("inferConfigurationPublication() accepted an unexpected source")
			}
			if _, err := os.Lstat(fixture.publicPath()); err != nil {
				t.Fatalf("unexpected source was not restored: %v", err)
			}
			if _, err := os.Lstat(privatePath); !os.IsNotExist(err) {
				t.Fatalf("unexpected retained source remains: %v", err)
			}
		})
	}
}
