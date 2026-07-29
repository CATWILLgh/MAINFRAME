package credentialmigration

import (
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func TestReviewLegacyTransferDraftAcceptsPartialChoicesWithoutWriteAuthority(
	t *testing.T,
) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(t, definitions, credentialcatalog.Instance{
		ID: "dokploy-existing", ServiceID: "dokploy",
		Name: "Existing", Purpose: "Existing deployments",
		Credentials: []credentialcatalog.CredentialBinding{{
			RoleID: "api-key",
			Secret: credentialcatalog.SecretReference{
				Backend: credentialcatalog.BackendSecretEnvironment,
				Name:    "SHARED_KEY",
			},
		}},
	})
	plan := legacyDraftPlan()
	draft := LegacyTransferDraft{
		ReleaseID: plan.ReleaseID,
		Choices: []LegacyTransferChoice{{
			Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
			ExpectedOccurrences: 2,
			Action:              TransferChoiceTransfer,
			TargetInstanceID:    "dokploy-existing",
			TargetRoleID:        "api-key",
		}},
	}

	review, err := ReviewLegacyTransferDraft(
		plan,
		current,
		definitions,
		draft,
	)
	if err != nil {
		t.Fatalf("ReviewLegacyTransferDraft() error = %v", err)
	}
	if review.TotalProposals != 2 ||
		review.TransferredProposals != 1 ||
		review.PendingProposals != 1 ||
		review.SkippedProposals != 0 ||
		!review.ManualContentReviewRequired ||
		review.RetirementReady {
		t.Fatalf("review status = %#v", review)
	}
	if len(review.Changes) != 0 ||
		!reflect.DeepEqual(review.Desired.All(), current.All()) {
		t.Fatalf("review changed current catalog = %#v", review)
	}
}

func TestReviewLegacyTransferDraftAllowsSharedReferenceAcrossTargets(
	t *testing.T,
) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(t, definitions)
	plan := legacyDraftPlan()
	newInstances := []credentialcatalog.Instance{
		legacyDraftInstance("dokploy-home", "Home", "SHARED_KEY"),
		legacyDraftInstance("dokploy-work", "Work", "SHARED_KEY"),
	}
	draft := LegacyTransferDraft{
		ReleaseID:    plan.ReleaseID,
		NewInstances: newInstances,
		Choices: []LegacyTransferChoice{
			{
				Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
				ExpectedOccurrences: 2,
				Action:              TransferChoiceTransfer,
				TargetInstanceID:    "dokploy-home",
				TargetRoleID:        "api-key",
			},
			{
				Proposal:            legacyDraftProposalIdentity(plan, 1, 0),
				ExpectedOccurrences: 1,
				Action:              TransferChoiceTransfer,
				TargetInstanceID:    "dokploy-work",
				TargetRoleID:        "api-key",
			},
		},
	}

	review, err := ReviewLegacyTransferDraft(
		plan,
		current,
		definitions,
		draft,
	)
	if err != nil {
		t.Fatalf("ReviewLegacyTransferDraft() error = %v", err)
	}
	if review.TransferredProposals != 2 ||
		review.PendingProposals != 0 ||
		len(review.Changes) != 2 ||
		len(review.Desired.All()) != 2 {
		t.Fatalf("review = %#v", review)
	}
}

func TestReviewLegacyTransferDraftRejectsContradictoryRename(t *testing.T) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(t, definitions)
	plan := legacyDraftPlan()
	draft := LegacyTransferDraft{
		ReleaseID: plan.ReleaseID,
		NewInstances: []credentialcatalog.Instance{
			legacyDraftInstance("dokploy-home", "Home", "RENAMED_HOME"),
			legacyDraftInstance("dokploy-work", "Work", "RENAMED_WORK"),
		},
		Choices: []LegacyTransferChoice{
			{
				Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
				ExpectedOccurrences: 2,
				Action:              TransferChoiceTransfer,
				TargetInstanceID:    "dokploy-home",
				TargetRoleID:        "api-key",
				RenameConfirmed:     true,
			},
			{
				Proposal:            legacyDraftProposalIdentity(plan, 1, 0),
				ExpectedOccurrences: 1,
				Action:              TransferChoiceTransfer,
				TargetInstanceID:    "dokploy-work",
				TargetRoleID:        "api-key",
				RenameConfirmed:     true,
			},
		},
	}

	if _, err := ReviewLegacyTransferDraft(
		plan,
		current,
		definitions,
		draft,
	); err == nil {
		t.Fatal("ReviewLegacyTransferDraft() error = nil")
	}
}

func TestReviewLegacyTransferDraftRejectsInvalidChoiceIdentity(
	t *testing.T,
) {
	definitions := legacyDraftDefinitions(t)
	current := legacyDraftInstances(t, definitions)
	plan := legacyDraftPlan()
	choice := LegacyTransferChoice{
		Proposal:            legacyDraftProposalIdentity(plan, 0, 0),
		ExpectedOccurrences: 2,
		Action:              TransferChoiceSkip,
		SkipReason:          TransferSkipObsolete,
	}

	for name, mutate := range map[string]func(*LegacyTransferDraft){
		"duplicate": func(draft *LegacyTransferDraft) {
			draft.Choices = append(draft.Choices, draft.Choices[0])
		},
		"unknown source role": func(draft *LegacyTransferDraft) {
			draft.Choices[0].Proposal.SourceRole = SourceRoleAdapterCopy
		},
		"stale occurrences": func(draft *LegacyTransferDraft) {
			draft.Choices[0].ExpectedOccurrences = 3
		},
		"stale release": func(draft *LegacyTransferDraft) {
			draft.ReleaseID = "stale-release"
		},
	} {
		t.Run(name, func(t *testing.T) {
			draft := LegacyTransferDraft{
				ReleaseID: plan.ReleaseID,
				Choices:   []LegacyTransferChoice{choice},
			}
			mutate(&draft)
			if _, err := ReviewLegacyTransferDraft(
				plan,
				current,
				definitions,
				draft,
			); err == nil {
				t.Fatal("ReviewLegacyTransferDraft() error = nil")
			}
		})
	}
}

func legacyDraftPlan() LegacyTransferPlan {
	return LegacyTransferPlan{
		ReleaseID:          "release-a",
		MigrationReadiness: ReadinessManualTransferRequired,
		SourceAccounting:   AccountingComplete,
		ContentAccounting:  AccountingPartial,
		Groups: []LegacyPlanGroup{
			{
				ComponentID:          domain.ComponentClaudeCode,
				ResourceID:           "claude-code.credentials-index",
				SourceRole:           SourceRoleSharedOriginal,
				SectionPath:          []string{"Catalog", "Home"},
				UnmappedContentLines: 1,
				Proposals: []LegacyCredentialProposal{{
					ReferenceName: "SHARED_KEY",
					Occurrences:   2,
					Compatibility: ReferenceCatalogCompatible,
				}},
			},
			{
				ComponentID: domain.ComponentCodex,
				ResourceID:  "codex.credentials-index",
				SourceRole:  SourceRoleAdapterCopy,
				SectionPath: []string{"Catalog", "Work"},
				Proposals: []LegacyCredentialProposal{{
					ReferenceName: "SHARED_KEY",
					Occurrences:   1,
					Compatibility: ReferenceCatalogCompatible,
				}},
			},
		},
	}
}

func legacyDraftProposalIdentity(
	plan LegacyTransferPlan,
	groupIndex int,
	proposalIndex int,
) LegacyProposalIdentity {
	group := plan.Groups[groupIndex]
	proposal := group.Proposals[proposalIndex]
	return LegacyProposalIdentity{
		ComponentID:   group.ComponentID,
		ResourceID:    group.ResourceID,
		SourceRole:    group.SourceRole,
		SectionPath:   append([]string(nil), group.SectionPath...),
		ReferenceName: proposal.ReferenceName,
	}
}

func legacyDraftDefinitions(t *testing.T) credentialcatalog.Definitions {
	t.Helper()
	payload := []byte(`{
		"schema_version":1,
		"kind":"mainframe-credential-definitions",
		"services":[{
			"id":"dokploy",
			"name":"Dokploy",
			"summary":"Deployment control plane.",
			"source":{"kind":"standalone"},
			"credential_roles":[{
				"id":"api-key",
				"name":"API key",
				"purpose":"Call the API.",
				"acquisition":"Create it."
			}]
		}]
	}`)
	definitions, err := credentialcatalog.ParseDefinitions(
		payload,
		mcpcatalog.Catalog{},
	)
	if err != nil {
		t.Fatalf("ParseDefinitions() error = %v", err)
	}
	return definitions
}

func legacyDraftInstances(
	t *testing.T,
	definitions credentialcatalog.Definitions,
	values ...credentialcatalog.Instance,
) credentialcatalog.Instances {
	t.Helper()
	instances, err := credentialcatalog.BuildInstances(values, definitions)
	if err != nil {
		t.Fatalf("BuildInstances() error = %v", err)
	}
	return instances
}

func legacyDraftInstance(
	id credentialcatalog.InstanceID,
	name string,
	reference string,
) credentialcatalog.Instance {
	return credentialcatalog.Instance{
		ID: id, ServiceID: "dokploy",
		Name: name, Purpose: name + " deployments",
		Credentials: []credentialcatalog.CredentialBinding{{
			RoleID: "api-key",
			Secret: credentialcatalog.SecretReference{
				Backend: credentialcatalog.BackendSecretEnvironment,
				Name:    reference,
			},
		}},
	}
}
