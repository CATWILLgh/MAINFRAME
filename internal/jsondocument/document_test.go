package jsondocument_test

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func TestParseAndLookupCanonicalOwnedValues(t *testing.T) {
	document, err := jsondocument.Parse([]byte(`{"permissions":{"allow":["Read"],"metadata":{"b":2,"a":1}}}`))
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	tests := map[string]string{
		"/permissions/allow":    `["Read"]`,
		"/permissions/metadata": `{"a":1,"b":2}`,
	}
	for raw, want := range tests {
		pointer, err := jsondocument.ParsePointer(raw)
		if err != nil {
			t.Fatalf("ParsePointer(%q) error = %v", raw, err)
		}
		got, status := document.Lookup(pointer)
		if status != jsondocument.Found || got != want {
			t.Fatalf("Lookup(%q) = %q, %q; want %q, found", raw, got, status, want)
		}
	}
}

func TestLookupOrderedPreservesObjectMemberOrder(t *testing.T) {
	document, err := jsondocument.Parse(
		[]byte(`{"permission":{"bash":{"rm -rf /":"deny", "*": "allow"}}}`),
	)
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	pointer, err := jsondocument.ParsePointer("/permission")
	if err != nil {
		t.Fatalf("ParsePointer() error = %v", err)
	}

	got, status := document.LookupOrdered(pointer)
	want := `{"bash":{"rm -rf /":"deny","*":"allow"}}`
	if status != jsondocument.Found || got != want {
		t.Fatalf("LookupOrdered() = %q, %q; want %q, found", got, status, want)
	}
}

func TestLookupDistinguishesMissingAndIncompatibleTraversal(t *testing.T) {
	document, err := jsondocument.Parse([]byte(`{"object":{},"array":[{"value":true}]}`))
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	tests := map[string]jsondocument.LookupStatus{
		"/object/missing": jsondocument.Missing,
		"/array/0":        jsondocument.Incompatible,
	}
	for raw, want := range tests {
		pointer, err := jsondocument.ParsePointer(raw)
		if err != nil {
			t.Fatalf("ParsePointer(%q) error = %v", raw, err)
		}
		_, got := document.Lookup(pointer)
		if got != want {
			t.Fatalf("Lookup(%q) status = %q, want %q", raw, got, want)
		}
	}
}

func TestParseRejectsAmbiguousOrMalformedJSON(t *testing.T) {
	tests := map[string][]byte{
		"duplicate key":      []byte(`{"value":1,"value":2}`),
		"invalid UTF-8":      {'{', '"', 'x', '"', ':', '"', 0xff, '"', '}'},
		"unpaired high":      []byte(`{"value":"\uD800"}`),
		"unpaired low":       []byte(`{"value":"\uDC00"}`),
		"invalid pair":       []byte(`{"value":"\uD800\u0041"}`),
		"trailing value":     []byte(`{} {}`),
		"malformed document": []byte(`{"value":`),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := jsondocument.Parse(payload); err == nil {
				t.Fatal("Parse() accepted invalid JSON")
			}
		})
	}
	if _, err := jsondocument.Parse([]byte(`{"value":"\uD83D\uDE00","literal":"�"}`)); err != nil {
		t.Fatalf("Parse() rejected valid Unicode = %v", err)
	}
}

func TestParsePointerImplementsRFC6901ObjectTokens(t *testing.T) {
	document, err := jsondocument.Parse([]byte(`{"a/b":{"~key":true}}`))
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	pointer, err := jsondocument.ParsePointer(`/a~1b/~0key`)
	if err != nil {
		t.Fatalf("ParsePointer() error = %v", err)
	}
	value, status := document.Lookup(pointer)
	if status != jsondocument.Found || value != "true" {
		t.Fatalf("Lookup() = %q, %q", value, status)
	}
	for _, raw := range []string{"", "permissions/allow", "/invalid~", "/invalid~2token"} {
		if _, err := jsondocument.ParsePointer(raw); err == nil {
			t.Fatalf("ParsePointer(%q) accepted invalid pointer", raw)
		}
	}
}

func TestPointersOverlapByDecodedTokenAncestry(t *testing.T) {
	parse := func(raw string) jsondocument.Pointer {
		t.Helper()
		pointer, err := jsondocument.ParsePointer(raw)
		if err != nil {
			t.Fatalf("ParsePointer(%q) error = %v", raw, err)
		}
		return pointer
	}
	tests := []struct {
		left, right string
		want        bool
	}{
		{left: "/permissions", right: "/permissions/allow", want: true},
		{left: "/a~1b", right: "/a~1b/value", want: true},
		{left: "/a~1b", right: "/a/b", want: false},
		{left: "/permissions/allow", right: "/permissions/deny", want: false},
	}
	for _, test := range tests {
		if got := jsondocument.Overlaps(parse(test.left), parse(test.right)); got != test.want {
			t.Fatalf("Overlaps(%q, %q) = %t, want %t", test.left, test.right, got, test.want)
		}
	}
}
