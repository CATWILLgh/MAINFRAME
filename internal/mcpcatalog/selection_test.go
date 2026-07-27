package mcpcatalog

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPreviewValidatesAndSortsAdapterSelections(t *testing.T) {
	catalog, err := Parse(validCatalogJSON())
	if err != nil {
		t.Fatalf("parse catalog: %v", err)
	}
	preview, err := catalog.Preview(
		[]domain.ComponentID{domain.ComponentCodex, domain.ComponentClaudeCode},
		[]Selection{{
			ServerID: "context7", ProfileID: "remote-api-key",
			Adapters: []domain.ComponentID{domain.ComponentCodex, domain.ComponentClaudeCode},
		}},
	)
	if err != nil {
		t.Fatalf("preview selection: %v", err)
	}
	want := []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentCodex}
	if !reflect.DeepEqual(preview.Connections[0].Adapters, want) {
		t.Fatalf("adapters = %v, want %v", preview.Connections[0].Adapters, want)
	}
	if preview.Executable {
		t.Fatal("onboarding preview must remain non-executable")
	}
}

func TestPreviewRejectsUnselectedAndDuplicateAdapters(t *testing.T) {
	catalog, err := Parse(validCatalogJSON())
	if err != nil {
		t.Fatalf("parse catalog: %v", err)
	}
	tests := map[string]Selection{
		"environment not selected": {
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentOpenCode},
		},
		"duplicate adapter": {
			ServerID: "context7", ProfileID: "remote-keyless",
			Adapters: []domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentClaudeCode},
		},
	}
	for name, selection := range tests {
		t.Run(name, func(t *testing.T) {
			_, err := catalog.Preview(
				[]domain.ComponentID{domain.ComponentClaudeCode, domain.ComponentAntigravity2},
				[]Selection{selection},
			)
			if err == nil || !strings.Contains(err.Error(), string(selection.Adapters[0])) {
				t.Fatalf("error = %v", err)
			}
		})
	}
}
