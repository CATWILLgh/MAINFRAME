package credentialmigration

import (
	"encoding/json"
	"io/fs"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestPreviewLegacyReferencesPreservesNamedUsesWithoutExamples(t *testing.T) {
	content := []byte(`# Credentials index

> Example: ` + "`secret get EXAMPLE_KEY`" + `

## VPS

<!-- ` + "`secret get COMMENT_KEY`" + ` -->

### Home
- API: ` + "`secret get SHARED_KEY`" + `
- Old login: ` + "`secret get legacy-login`" + `
- Repeated pointer: ` + "`secret get SHARED_KEY`" + `

### Work
- API: ` + "`secret get SHARED_KEY`" + `

~~~text
secret get FENCED_EXAMPLE
~~~
`)

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if preview.TotalReferenceMentions != 7 ||
		preview.ExtractedReferenceMentions != 4 ||
		preview.ExcludedReferenceMentions != 3 ||
		preview.ExcludedExampleMentions != 3 ||
		preview.MalformedReferenceMentions != 0 ||
		preview.UnscopedReferenceMentions != 0 {
		t.Fatalf("preview counts = %#v", preview)
	}
	want := []LegacyReferenceGroup{
		{
			SectionPath: []string{"Credentials index", "VPS", "Home"},
			References: []LegacyReference{{
				Name: "SHARED_KEY", Occurrences: 2,
				Compatibility: ReferenceCatalogCompatible,
			}, {
				Name: "legacy-login", Occurrences: 1,
				Compatibility: ReferenceLegacyName,
			}},
		},
		{
			SectionPath: []string{"Credentials index", "VPS", "Work"},
			References: []LegacyReference{{
				Name: "SHARED_KEY", Occurrences: 1,
				Compatibility: ReferenceCatalogCompatible,
			}},
		},
	}
	if !reflect.DeepEqual(preview.Groups, want) {
		t.Fatalf("preview groups = %#v, want %#v", preview.Groups, want)
	}
}

func TestPreviewLegacyReferencesCountsUnscopedAndMalformedMentions(t *testing.T) {
	content := []byte("secret get BEFORE_HEADING\n# Catalog\nsecret get 9BAD\n")

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if len(preview.Groups) != 0 ||
		preview.TotalReferenceMentions != 2 ||
		preview.ExtractedReferenceMentions != 0 ||
		preview.ExcludedReferenceMentions != 2 ||
		preview.MalformedReferenceMentions != 1 ||
		preview.UnscopedReferenceMentions != 1 {
		t.Fatalf("preview = %#v", preview)
	}
}

func TestPreviewLegacyReferencesDoesNotPartiallyExtractInvalidToken(
	t *testing.T,
) {
	content := []byte(
		"# Catalog\n" +
			"secret get GOOD.bad\n" +
			"secret get $(PRIVATE_KEY)\n" +
			"secret get VALID_KEY.\n",
	)

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if preview.ExtractedReferenceMentions != 1 ||
		preview.MalformedReferenceMentions != 2 ||
		preview.Groups[0].References[0].Name != "VALID_KEY" {
		t.Fatalf("preview = %#v", preview)
	}
}

func TestPreviewLegacyReferencesCountsUnmappedDescriptions(t *testing.T) {
	content := []byte(
		"# Catalog\n\n## Work\n- Purpose: deployment\n---\n" +
			"- Token: `secret get WORK_KEY`\n",
	)

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if preview.UnmappedContentLines != 1 {
		t.Fatalf("unmapped content lines = %d", preview.UnmappedContentLines)
	}
}

func TestPreviewLegacyReferencesRejectsUnsafeText(t *testing.T) {
	for name, content := range map[string][]byte{
		"invalid UTF-8": {0xff},
		"NUL byte":      {'#', ' ', 'A', 0, '\n'},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := PreviewLegacyReferences(content); err == nil {
				t.Fatal("PreviewLegacyReferences() error = nil")
			}
		})
	}
}

func TestInspectLegacyReferencePreviewReadsOnlySharedOriginal(t *testing.T) {
	release := legacyReleaseFixture()
	canary := "secret get PRIVATE_CANARY"
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{
			release.Resources[0].Target: {
				Kind: hostfs.EntryRegular, Mode: 0o600,
				Content: []byte("# Catalog\n## Work\n" + canary + "\n"),
			},
		},
		errors: map[domain.Location]error{
			release.Resources[1].Target: fs.ErrNotExist,
			release.Resources[2].Target: fs.ErrNotExist,
			release.Resources[3].Target: fs.ErrNotExist,
		},
	}

	preview, err := InspectLegacyReferencePreview(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyReferencePreview() error = %v", err)
	}
	if preview.Indexes[0].SourceRole != SourceRoleSharedOriginal ||
		preview.MigrationReadiness != ReadinessManualTransferRequired ||
		preview.References.ExtractedReferenceMentions != 1 {
		t.Fatalf("preview = %#v", preview)
	}
	payload, err := json.Marshal(preview)
	if err != nil {
		t.Fatalf("marshal preview: %v", err)
	}
	if strings.Contains(string(payload), "secret get") {
		t.Fatalf("preview exposed source text: %s", payload)
	}
	if len(inspector.inspected) != 4 {
		t.Fatalf("inspected locations = %#v", inspector.inspected)
	}
}

func TestInspectLegacyReferencePreviewBlocksMalformedSource(t *testing.T) {
	release := legacyReleaseFixture()
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{
			release.Resources[0].Target: {
				Kind: hostfs.EntryRegular, Mode: 0o600,
				Content: []byte{0xff},
			},
		},
		errors: map[domain.Location]error{},
	}

	preview, err := InspectLegacyReferencePreview(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyReferencePreview() error = %v", err)
	}
	if preview.Indexes[0].State != IndexUnsafe ||
		preview.Indexes[0].UnsafeReason != ReasonMalformedContent ||
		preview.Indexes[0].MigrationReadiness != ReadinessBlocked ||
		len(preview.References.Groups) != 0 {
		t.Fatalf("preview = %#v", preview)
	}
}

func TestPreviewLegacyReferencesExcludesUnsafeHeadingText(t *testing.T) {
	content := []byte("# Catalog\n## Work\x1b[2J\nsecret get PRIVATE_KEY\n")

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if len(preview.Groups) != 1 ||
		!reflect.DeepEqual(
			preview.Groups[0].SectionPath,
			[]string{"Catalog"},
		) ||
		preview.ExcludedReferenceMentions != 0 {
		t.Fatalf("preview = %#v", preview)
	}
}
