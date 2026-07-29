package credentialmigration

import (
	"io/fs"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestInspectLegacyTransferPlanKeepsSourcesIndependent(t *testing.T) {
	release := legacyReleaseFixture()
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{
			release.Resources[0].Target: legacyPlanEntry(
				"# Catalog\n## Home\n- note\nsecret get SHARED_KEY\n",
			),
			release.Resources[1].Target: legacyPlanEntry(
				"# Catalog\n## Work\nsecret get SHARED_KEY\nsecret get legacy-key\n",
			),
			release.Resources[2].Target: legacyPlanEntry(
				"# Catalog\n## Work\nsecret get SHARED_KEY\nsecret get legacy-key\n",
			),
		},
		errors: map[domain.Location]error{
			release.Resources[3].Target: fs.ErrNotExist,
		},
	}

	plan, err := InspectLegacyTransferPlan(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyTransferPlan() error = %v", err)
	}
	if plan.MigrationReadiness != ReadinessManualTransferRequired ||
		plan.SourceAccounting != AccountingComplete ||
		plan.ContentAccounting != AccountingPartial {
		t.Fatalf("plan accounting = %#v", plan)
	}
	if len(plan.Sources) != 4 || len(plan.Groups) != 3 {
		t.Fatalf("plan shape = %#v", plan)
	}
	for _, group := range plan.Groups {
		if group.ResourceID == "" || group.ComponentID == "" ||
			group.SourceRole == "" {
			t.Fatalf("group lost source provenance: %#v", group)
		}
		for _, proposal := range group.Proposals {
			wantFields := []TargetField{
				TargetFieldInstanceID,
				TargetFieldServiceID,
				TargetFieldRoleID,
				TargetFieldName,
				TargetFieldPurpose,
			}
			if !reflect.DeepEqual(proposal.UnresolvedFields, wantFields) {
				t.Fatalf("unresolved fields = %v", proposal.UnresolvedFields)
			}
		}
	}
	if len(plan.Relationships) != 3 {
		t.Fatalf("relationships = %#v", plan.Relationships)
	}
	if plan.Groups[0].UnmappedContentLines != 1 {
		t.Fatalf("per-section unmapped lines = %#v", plan.Groups[0])
	}
}

func TestInspectLegacyTransferPlanRetainsSafeResultsWhenOneSourceBlocks(
	t *testing.T,
) {
	release := legacyReleaseFixture()
	inspector := &legacyInspectorFixture{
		entries: map[domain.Location]hostfs.Entry{
			release.Resources[0].Target: legacyPlanEntry(
				"# Catalog\n## Home\nsecret get SAFE_KEY\n",
			),
			release.Resources[1].Target: {
				Kind: hostfs.EntryRegular,
				Mode: 0o644,
			},
		},
		errors: map[domain.Location]error{
			release.Resources[2].Target: fs.ErrNotExist,
			release.Resources[3].Target: fs.ErrNotExist,
		},
	}

	plan, err := InspectLegacyTransferPlan(release, inspector)
	if err != nil {
		t.Fatalf("InspectLegacyTransferPlan() error = %v", err)
	}
	if plan.MigrationReadiness != ReadinessBlocked ||
		plan.SourceAccounting != AccountingComplete ||
		plan.ContentAccounting != AccountingBlocked {
		t.Fatalf("blocked plan accounting = %#v", plan)
	}
	if len(plan.Groups) != 1 ||
		plan.Groups[0].Proposals[0].ReferenceName != "SAFE_KEY" {
		t.Fatalf("safe result was discarded: %#v", plan.Groups)
	}
}

func TestPreviewLegacyReferencesAccountsForEveryMeaningfulLine(t *testing.T) {
	content := []byte(
		"secret get BEFORE_HEADING\n" +
			"# \x01invalid\n" +
			"# Catalog\n" +
			"## Work\n" +
			"description\n" +
			"secret get 9BAD\n" +
			"secret get VALID_KEY\n" +
			"~~~\n" +
			"example text\n",
	)

	preview, err := PreviewLegacyReferences(content)
	if err != nil {
		t.Fatalf("PreviewLegacyReferences() error = %v", err)
	}
	if preview.UnscopedReferenceMentions != 1 ||
		preview.MalformedReferenceMentions != 1 ||
		preview.InvalidHeadingLines != 1 ||
		preview.ExcludedContentLines != 2 ||
		preview.UnmappedContentLines != 2 ||
		preview.Groups[0].UnmappedContentLines != 2 {
		t.Fatalf("line accounting = %#v", preview)
	}
}

func TestLegacyPlanRelationshipsKeepAmbiguousHeadingPathsDistinct(
	t *testing.T,
) {
	groups := []LegacyPlanGroup{
		{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SectionPath: []string{"Catalog", "A/B"},
			Proposals: []LegacyCredentialProposal{{
				ReferenceName: "SHARED_KEY",
			}},
		},
		{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SectionPath: []string{"Catalog", "A", "B"},
			Proposals: []LegacyCredentialProposal{{
				ReferenceName: "SHARED_KEY",
			}},
		},
	}

	relationships := legacyPlanRelationships(groups)
	if len(relationships) != 2 ||
		relationships[0].Kind != RelationshipSharedReference {
		t.Fatalf("relationships = %#v", relationships)
	}
	want := []LegacyPlanGroupIdentity{
		{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SectionPath: []string{"Catalog", "A/B"},
		},
		{
			ComponentID: domain.ComponentClaudeCode,
			ResourceID:  "claude-code.credentials-index",
			SectionPath: []string{"Catalog", "A", "B"},
		},
	}
	if !reflect.DeepEqual(relationships[0].Groups, want) {
		t.Fatalf("relationship groups = %#v, want %#v", relationships[0].Groups, want)
	}
}

func legacyPlanEntry(content string) hostfs.Entry {
	return hostfs.Entry{
		Kind:    hostfs.EntryRegular,
		Mode:    0o600,
		Content: []byte(content),
	}
}
