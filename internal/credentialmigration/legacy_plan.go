package credentialmigration

import (
	"sort"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type AccountingState string

const (
	AccountingComplete AccountingState = "complete"
	AccountingPartial  AccountingState = "partial"
	AccountingBlocked  AccountingState = "blocked"
)

type TargetField string

const (
	TargetFieldInstanceID TargetField = "instance_id"
	TargetFieldServiceID  TargetField = "service_id"
	TargetFieldRoleID     TargetField = "role_id"
	TargetFieldName       TargetField = "name"
	TargetFieldPurpose    TargetField = "purpose"
)

type ProposalDecision string

const (
	DecisionNeedsReview ProposalDecision = "needs_review"
	DecisionNeedsRename ProposalDecision = "needs_rename"
)

type RelationshipKind string

const (
	RelationshipSharedReference   RelationshipKind = "shared_reference"
	RelationshipPossibleDuplicate RelationshipKind = "possible_duplicate"
)

type LegacyTransferPlan struct {
	ReleaseID          string
	MigrationReadiness Readiness
	SourceAccounting   AccountingState
	ContentAccounting  AccountingState
	Sources            []LegacyPlanSource
	Groups             []LegacyPlanGroup
	Relationships      []LegacyPlanRelationship
}

type LegacyPlanSource struct {
	ComponentID        domain.ComponentID
	ResourceID         string
	SourceRole         SourceRole
	State              IndexState
	UnsafeReason       UnsafeReason
	MigrationReadiness Readiness
	ContentAccounting  AccountingState
	Summary            LegacyReferencePreview
}

type LegacyPlanGroup struct {
	ComponentID          domain.ComponentID
	ResourceID           string
	SourceRole           SourceRole
	SectionPath          []string
	UnmappedContentLines int
	Proposals            []LegacyCredentialProposal
}

type LegacyCredentialProposal struct {
	ReferenceName    string
	Occurrences      int
	Compatibility    ReferenceCompatibility
	SuggestedBackend string
	Decision         ProposalDecision
	UnresolvedFields []TargetField
}

type LegacyPlanRelationship struct {
	Kind          RelationshipKind
	ReferenceName string
	Groups        []LegacyPlanGroupIdentity
}

type LegacyPlanGroupIdentity struct {
	ComponentID domain.ComponentID
	ResourceID  string
	SectionPath []string
}

var unresolvedLegacyTargetFields = []TargetField{
	TargetFieldInstanceID,
	TargetFieldServiceID,
	TargetFieldRoleID,
	TargetFieldName,
	TargetFieldPurpose,
}

func InspectLegacyTransferPlan(
	release releasecontract.Release,
	inspector Inspector,
) (LegacyTransferPlan, error) {
	resources, err := legacyResources(release.Resources)
	if err != nil {
		return LegacyTransferPlan{}, err
	}
	plan := LegacyTransferPlan{
		ReleaseID:         release.ID,
		SourceAccounting:  AccountingComplete,
		ContentAccounting: AccountingComplete,
	}
	indexes := make([]LegacyIndex, 0, len(resources))
	for index, resource := range resources {
		source, preview := inspectLegacyReferenceSourceWithRole(
			resource,
			legacyResourceDescriptors[index].sourceRole,
			inspector,
		)
		indexes = append(indexes, source)
		plan.Sources = append(plan.Sources, legacyPlanSource(source, preview))
		plan.Groups = append(
			plan.Groups,
			legacyPlanGroups(source, preview)...,
		)
	}
	plan.MigrationReadiness = reduceReadiness(indexes)
	plan.ContentAccounting = reduceContentAccounting(plan.Sources)
	plan.Relationships = legacyPlanRelationships(plan.Groups)
	return plan, nil
}

func inspectLegacyReferenceSourceWithRole(
	resource releasecontract.Resource,
	role SourceRole,
	inspector Inspector,
) (LegacyIndex, LegacyReferencePreview) {
	source, preview := inspectLegacyReferenceSource(resource, inspector)
	source.SourceRole = role
	return source, preview
}

func legacyPlanSource(
	source LegacyIndex,
	preview LegacyReferencePreview,
) LegacyPlanSource {
	return LegacyPlanSource{
		ComponentID:        source.ComponentID,
		ResourceID:         source.ResourceID,
		SourceRole:         source.SourceRole,
		State:              source.State,
		UnsafeReason:       source.UnsafeReason,
		MigrationReadiness: source.MigrationReadiness,
		ContentAccounting:  sourceContentAccounting(source, preview),
		Summary:            preview,
	}
}

func sourceContentAccounting(
	source LegacyIndex,
	preview LegacyReferencePreview,
) AccountingState {
	if source.MigrationReadiness == ReadinessBlocked {
		return AccountingBlocked
	}
	if source.MigrationReadiness == ReadinessNoTransferRequired {
		return AccountingComplete
	}
	if preview.ExcludedReferenceMentions > 0 ||
		preview.UnmappedContentLines > 0 ||
		preview.InvalidHeadingLines > 0 ||
		preview.ExcludedContentLines > 0 {
		return AccountingPartial
	}
	return AccountingComplete
}

func reduceContentAccounting(sources []LegacyPlanSource) AccountingState {
	result := AccountingComplete
	for _, source := range sources {
		if source.ContentAccounting == AccountingBlocked {
			return AccountingBlocked
		}
		if source.ContentAccounting == AccountingPartial {
			result = AccountingPartial
		}
	}
	return result
}

func legacyPlanGroups(
	source LegacyIndex,
	preview LegacyReferencePreview,
) []LegacyPlanGroup {
	result := make([]LegacyPlanGroup, 0, len(preview.Groups))
	indexes := make(map[string]int)
	for _, group := range preview.Groups {
		proposals := make([]LegacyCredentialProposal, len(group.References))
		for index, reference := range group.References {
			proposals[index] = legacyProposal(reference)
		}
		indexes[strings.Join(group.SectionPath, "\x00")] = len(result)
		result = append(result, LegacyPlanGroup{
			ComponentID:          source.ComponentID,
			ResourceID:           source.ResourceID,
			SourceRole:           source.SourceRole,
			SectionPath:          append([]string(nil), group.SectionPath...),
			UnmappedContentLines: group.UnmappedContentLines,
			Proposals:            proposals,
		})
	}
	for _, section := range preview.Sections {
		key := strings.Join(section.SectionPath, "\x00")
		if index, exists := indexes[key]; exists {
			result[index].UnmappedContentLines = section.UnmappedContentLines
			continue
		}
		result = append(result, LegacyPlanGroup{
			ComponentID:          source.ComponentID,
			ResourceID:           source.ResourceID,
			SourceRole:           source.SourceRole,
			SectionPath:          append([]string(nil), section.SectionPath...),
			UnmappedContentLines: section.UnmappedContentLines,
		})
	}
	return result
}

func legacyProposal(reference LegacyReference) LegacyCredentialProposal {
	decision := DecisionNeedsReview
	backend := "secret-env"
	if reference.Compatibility == ReferenceLegacyName {
		decision = DecisionNeedsRename
		backend = ""
	}
	return LegacyCredentialProposal{
		ReferenceName:    reference.Name,
		Occurrences:      reference.Occurrences,
		Compatibility:    reference.Compatibility,
		SuggestedBackend: backend,
		Decision:         decision,
		UnresolvedFields: append(
			[]TargetField(nil),
			unresolvedLegacyTargetFields...,
		),
	}
}

func legacyPlanRelationships(
	groups []LegacyPlanGroup,
) []LegacyPlanRelationship {
	var relationships []LegacyPlanRelationship
	relationships = append(relationships, sharedReferenceRelationships(groups)...)
	relationships = append(relationships, possibleDuplicateRelationships(groups)...)
	return relationships
}

func sharedReferenceRelationships(
	groups []LegacyPlanGroup,
) []LegacyPlanRelationship {
	uses := make(map[string][]LegacyPlanGroupIdentity)
	for _, group := range groups {
		identity := legacyGroupIdentity(group)
		for _, proposal := range group.Proposals {
			uses[proposal.ReferenceName] = append(
				uses[proposal.ReferenceName],
				identity,
			)
		}
	}
	names := make([]string, 0, len(uses))
	for name, keys := range uses {
		if len(keys) > 1 {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	result := make([]LegacyPlanRelationship, 0, len(names))
	for _, name := range names {
		result = append(result, LegacyPlanRelationship{
			Kind:          RelationshipSharedReference,
			ReferenceName: name,
			Groups:        cloneLegacyGroupIdentities(uses[name]),
		})
	}
	return result
}

func possibleDuplicateRelationships(
	groups []LegacyPlanGroup,
) []LegacyPlanRelationship {
	signatures := make(map[string][]LegacyPlanGroupIdentity)
	for _, group := range groups {
		names := make([]string, len(group.Proposals))
		for index, proposal := range group.Proposals {
			names[index] = proposal.ReferenceName
		}
		sort.Strings(names)
		signatures[strings.Join(names, "\x00")] = append(
			signatures[strings.Join(names, "\x00")],
			legacyGroupIdentity(group),
		)
	}
	keys := make([]string, 0, len(signatures))
	for signature, members := range signatures {
		if signature != "" && len(members) > 1 {
			keys = append(keys, signature)
		}
	}
	sort.Strings(keys)
	result := make([]LegacyPlanRelationship, 0, len(keys))
	for _, signature := range keys {
		result = append(result, LegacyPlanRelationship{
			Kind:   RelationshipPossibleDuplicate,
			Groups: cloneLegacyGroupIdentities(signatures[signature]),
		})
	}
	return result
}

func legacyGroupIdentity(group LegacyPlanGroup) LegacyPlanGroupIdentity {
	return LegacyPlanGroupIdentity{
		ComponentID: group.ComponentID,
		ResourceID:  group.ResourceID,
		SectionPath: append([]string(nil), group.SectionPath...),
	}
}

func cloneLegacyGroupIdentities(
	source []LegacyPlanGroupIdentity,
) []LegacyPlanGroupIdentity {
	result := make([]LegacyPlanGroupIdentity, len(source))
	for index, identity := range source {
		result[index] = identity
		result[index].SectionPath = append(
			[]string(nil),
			identity.SectionPath...,
		)
	}
	return result
}
