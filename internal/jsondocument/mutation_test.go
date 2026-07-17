package jsondocument_test

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func TestSetPreservesObjectOrderAndCreatesMissingObjects(t *testing.T) {
	document, err := jsondocument.Parse([]byte(
		`{"z":1,"permission":{"bash":"ask"},"a":2}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	permission, err := jsondocument.ParsePointer("/permission")
	if err != nil {
		t.Fatal(err)
	}
	document, err = document.Set(
		permission,
		[]byte(`{"custom_*":"deny","bash":"allow","edit":"deny"}`),
	)
	if err != nil {
		t.Fatalf("Set(permission) error = %v", err)
	}
	nested, err := jsondocument.ParsePointer("/agent/build/permission")
	if err != nil {
		t.Fatal(err)
	}
	document, err = document.Set(nested, []byte(`{"write":"deny"}`))
	if err != nil {
		t.Fatalf("Set(nested) error = %v", err)
	}

	want := strings.Join([]string{
		"{",
		`  "z": 1,`,
		`  "permission": {`,
		`    "custom_*": "deny",`,
		`    "bash": "allow",`,
		`    "edit": "deny"`,
		"  },",
		`  "a": 2,`,
		`  "agent": {`,
		`    "build": {`,
		`      "permission": {`,
		`        "write": "deny"`,
		"      }",
		"    }",
		"  }",
		"}",
		"",
	}, "\n")
	if got := string(document.Indented()); got != want {
		t.Fatalf("Indented() =\n%s\nwant:\n%s", got, want)
	}
}

func TestSetRejectsIncompatibleParentWithoutMutatingDocument(t *testing.T) {
	document, err := jsondocument.Parse([]byte(`{"agent":"user-owned"}`))
	if err != nil {
		t.Fatal(err)
	}
	pointer, err := jsondocument.ParsePointer("/agent/build")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := document.Set(pointer, []byte(`{}`)); err == nil {
		t.Fatal("Set() accepted an incompatible parent")
	}
	if got := string(document.Raw()); got != `{"agent":"user-owned"}` {
		t.Fatalf("failed Set() mutated document: %q", got)
	}
}

func TestDeletePreservesSiblingOrderAndMissingPathsAreIdempotent(t *testing.T) {
	document, err := jsondocument.Parse([]byte(
		`{"version":1,"servers":{"alpha":{"url":"a"},"context7":{"url":"c"},"zeta":{"url":"z"}}}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	pointer, err := jsondocument.ParsePointer("/servers/context7")
	if err != nil {
		t.Fatal(err)
	}
	document, err = document.Delete(pointer)
	if err != nil {
		t.Fatalf("Delete() error = %v", err)
	}
	document, err = document.Delete(pointer)
	if err != nil {
		t.Fatalf("second Delete() error = %v", err)
	}
	want := strings.Join([]string{
		"{",
		`  "version": 1,`,
		`  "servers": {`,
		`    "alpha": {`,
		`      "url": "a"`,
		"    },",
		`    "zeta": {`,
		`      "url": "z"`,
		"    }",
		"  }",
		"}",
		"",
	}, "\n")
	if got := string(document.Indented()); got != want {
		t.Fatalf("Indented() =\n%s\nwant:\n%s", got, want)
	}
}

func TestDeleteRejectsAnIncompatibleParent(t *testing.T) {
	document, err := jsondocument.Parse([]byte(`{"servers":"user-owned"}`))
	if err != nil {
		t.Fatal(err)
	}
	pointer, err := jsondocument.ParsePointer("/servers/context7")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := document.Delete(pointer); err == nil {
		t.Fatal("Delete() accepted an incompatible parent")
	}
}
