package credentialmigration

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type TransferChoiceAction string

const (
	TransferChoiceTransfer TransferChoiceAction = "transfer"
	TransferChoiceSkip     TransferChoiceAction = "skip"
)

type TransferSkipReason string

const (
	TransferSkipDuplicate       TransferSkipReason = "duplicate"
	TransferSkipObsolete        TransferSkipReason = "obsolete"
	TransferSkipNotTransferable TransferSkipReason = "not_transferable"
)

type LegacyProposalIdentity struct {
	ComponentID   domain.ComponentID
	ResourceID    string
	SourceRole    SourceRole
	SectionPath   []string
	ReferenceName string
}

type LegacyTransferChoice struct {
	Proposal            LegacyProposalIdentity
	ExpectedOccurrences int
	Action              TransferChoiceAction
	TargetInstanceID    credentialcatalog.InstanceID
	TargetRoleID        credentialcatalog.RoleID
	RenameConfirmed     bool
	SkipReason          TransferSkipReason
}

type LegacyTransferDraft struct {
	ReleaseID    string
	NewInstances []credentialcatalog.Instance
	Choices      []LegacyTransferChoice
}

type TransferChoiceDisposition string

const (
	ChoicePending     TransferChoiceDisposition = "pending"
	ChoiceTransferred TransferChoiceDisposition = "transferred"
	ChoiceSkipped     TransferChoiceDisposition = "skipped"
)

type LegacyTransferChoiceResult struct {
	Proposal         LegacyProposalIdentity
	Occurrences      int
	Disposition      TransferChoiceDisposition
	TargetInstanceID credentialcatalog.InstanceID
	TargetRoleID     credentialcatalog.RoleID
	SkipReason       TransferSkipReason
}

type LegacyTransferDraftReview struct {
	Desired                     credentialcatalog.Instances
	Changes                     []credentialcatalog.InstanceChange
	Choices                     []LegacyTransferChoiceResult
	TotalProposals              int
	TransferredProposals        int
	SkippedProposals            int
	PendingProposals            int
	ManualContentReviewRequired bool
	RetirementReady             bool
}

type legacyPlanProposal struct {
	identity    LegacyProposalIdentity
	occurrences int
}

func ReviewLegacyTransferDraft(
	plan LegacyTransferPlan,
	current credentialcatalog.Instances,
	definitions credentialcatalog.Definitions,
	draft LegacyTransferDraft,
) (LegacyTransferDraftReview, error) {
	if draft.ReleaseID == "" || draft.ReleaseID != plan.ReleaseID {
		return LegacyTransferDraftReview{}, fmt.Errorf(
			"legacy transfer draft release is stale",
		)
	}
	desired, newIDs, err := buildLegacyDraftDesired(
		current,
		definitions,
		draft.NewInstances,
	)
	if err != nil {
		return LegacyTransferDraftReview{}, err
	}
	proposals := legacyPlanProposals(plan)
	choices, err := indexLegacyTransferChoices(proposals, draft.Choices)
	if err != nil {
		return LegacyTransferDraftReview{}, err
	}
	review, usedNewIDs, err := reviewLegacyChoices(
		proposals,
		choices,
		desired,
	)
	if err != nil {
		return LegacyTransferDraftReview{}, err
	}
	if err := requireUsedLegacyDraftInstances(newIDs, usedNewIDs); err != nil {
		return LegacyTransferDraftReview{}, err
	}
	review.Desired = desired
	review.Changes, err = credentialcatalog.PlanInstanceChanges(current, desired)
	if err != nil {
		return LegacyTransferDraftReview{}, err
	}
	review.ManualContentReviewRequired =
		plan.ContentAccounting != AccountingComplete
	review.RetirementReady = legacyDraftRetirementReady(plan, review)
	return review, nil
}

func buildLegacyDraftDesired(
	current credentialcatalog.Instances,
	definitions credentialcatalog.Definitions,
	newInstances []credentialcatalog.Instance,
) (
	credentialcatalog.Instances,
	map[credentialcatalog.InstanceID]struct{},
	error,
) {
	newIDs := make(map[credentialcatalog.InstanceID]struct{}, len(newInstances))
	for _, instance := range newInstances {
		if _, exists := newIDs[instance.ID]; exists {
			return credentialcatalog.Instances{}, nil, fmt.Errorf(
				"legacy transfer draft repeats new instance %q",
				instance.ID,
			)
		}
		newIDs[instance.ID] = struct{}{}
	}
	desired, err := credentialcatalog.BuildInstances(
		append(current.All(), newInstances...),
		definitions,
	)
	if err != nil {
		return credentialcatalog.Instances{}, nil, err
	}
	return desired, newIDs, nil
}

func legacyPlanProposals(plan LegacyTransferPlan) []legacyPlanProposal {
	var result []legacyPlanProposal
	for _, group := range plan.Groups {
		for _, proposal := range group.Proposals {
			result = append(result, legacyPlanProposal{
				identity: LegacyProposalIdentity{
					ComponentID: group.ComponentID,
					ResourceID:  group.ResourceID,
					SourceRole:  group.SourceRole,
					SectionPath: append(
						[]string(nil),
						group.SectionPath...,
					),
					ReferenceName: proposal.ReferenceName,
				},
				occurrences: proposal.Occurrences,
			})
		}
	}
	return result
}

func indexLegacyTransferChoices(
	proposals []legacyPlanProposal,
	choices []LegacyTransferChoice,
) (map[string]LegacyTransferChoice, error) {
	known := make(map[string]int, len(proposals))
	for _, proposal := range proposals {
		known[legacyProposalIdentityKey(proposal.identity)] =
			proposal.occurrences
	}
	result := make(map[string]LegacyTransferChoice, len(choices))
	for _, choice := range choices {
		key := legacyProposalIdentityKey(choice.Proposal)
		occurrences, exists := known[key]
		if !exists || occurrences != choice.ExpectedOccurrences {
			return nil, fmt.Errorf(
				"legacy transfer choice does not match the current plan",
			)
		}
		if _, exists := result[key]; exists {
			return nil, fmt.Errorf(
				"legacy transfer draft repeats one proposal choice",
			)
		}
		result[key] = choice
	}
	return result, nil
}

func reviewLegacyChoices(
	proposals []legacyPlanProposal,
	choices map[string]LegacyTransferChoice,
	desired credentialcatalog.Instances,
) (
	LegacyTransferDraftReview,
	map[credentialcatalog.InstanceID]struct{},
	error,
) {
	review := LegacyTransferDraftReview{
		TotalProposals: len(proposals),
		Choices:        make([]LegacyTransferChoiceResult, 0, len(proposals)),
	}
	usedNewIDs := make(map[credentialcatalog.InstanceID]struct{})
	renames := make(map[string]string)
	for _, proposal := range proposals {
		choice, exists := choices[legacyProposalIdentityKey(proposal.identity)]
		if !exists {
			review.PendingProposals++
			review.Choices = append(
				review.Choices,
				legacyPendingChoiceResult(proposal),
			)
			continue
		}
		result, reference, err := reviewLegacyChoice(proposal, choice, desired)
		if err != nil {
			return LegacyTransferDraftReview{}, nil, err
		}
		if result.Disposition == ChoiceSkipped {
			review.SkippedProposals++
		} else {
			if previous, exists := renames[proposal.identity.ReferenceName]; exists &&
				previous != reference {
				return LegacyTransferDraftReview{}, nil, fmt.Errorf(
					"one legacy reference maps to conflicting target names",
				)
			}
			renames[proposal.identity.ReferenceName] = reference
			review.TransferredProposals++
			usedNewIDs[result.TargetInstanceID] = struct{}{}
		}
		review.Choices = append(review.Choices, result)
	}
	return review, usedNewIDs, nil
}

func reviewLegacyChoice(
	proposal legacyPlanProposal,
	choice LegacyTransferChoice,
	desired credentialcatalog.Instances,
) (LegacyTransferChoiceResult, string, error) {
	switch choice.Action {
	case TransferChoiceSkip:
		if !validTransferSkipReason(choice.SkipReason) ||
			choice.TargetInstanceID != "" || choice.TargetRoleID != "" ||
			choice.RenameConfirmed {
			return LegacyTransferChoiceResult{}, "", fmt.Errorf(
				"legacy skip choice is invalid",
			)
		}
		return LegacyTransferChoiceResult{
			Proposal: proposal.identity, Occurrences: proposal.occurrences,
			Disposition: ChoiceSkipped, SkipReason: choice.SkipReason,
		}, "", nil
	case TransferChoiceTransfer:
		if choice.SkipReason != "" {
			return LegacyTransferChoiceResult{}, "", fmt.Errorf(
				"legacy transfer choice cannot include a skip reason",
			)
		}
		binding, exists := legacyDraftTargetBinding(
			desired,
			choice.TargetInstanceID,
			choice.TargetRoleID,
		)
		if !exists {
			return LegacyTransferChoiceResult{}, "", fmt.Errorf(
				"legacy transfer target does not exist",
			)
		}
		renamed := binding.Secret.Name != proposal.identity.ReferenceName
		if renamed != choice.RenameConfirmed {
			return LegacyTransferChoiceResult{}, "", fmt.Errorf(
				"legacy transfer rename confirmation is invalid",
			)
		}
		return LegacyTransferChoiceResult{
			Proposal: proposal.identity, Occurrences: proposal.occurrences,
			Disposition:      ChoiceTransferred,
			TargetInstanceID: choice.TargetInstanceID,
			TargetRoleID:     choice.TargetRoleID,
		}, binding.Secret.Name, nil
	default:
		return LegacyTransferChoiceResult{}, "", fmt.Errorf(
			"legacy transfer choice action is invalid",
		)
	}
}

func legacyDraftTargetBinding(
	instances credentialcatalog.Instances,
	instanceID credentialcatalog.InstanceID,
	roleID credentialcatalog.RoleID,
) (credentialcatalog.CredentialBinding, bool) {
	for _, instance := range instances.All() {
		if instance.ID != instanceID {
			continue
		}
		for _, binding := range instance.Credentials {
			if binding.RoleID == roleID {
				return binding, true
			}
		}
	}
	return credentialcatalog.CredentialBinding{}, false
}

func requireUsedLegacyDraftInstances(
	newIDs map[credentialcatalog.InstanceID]struct{},
	usedIDs map[credentialcatalog.InstanceID]struct{},
) error {
	for id := range newIDs {
		if _, exists := usedIDs[id]; !exists {
			return fmt.Errorf(
				"legacy transfer draft contains unused new instance %q",
				id,
			)
		}
	}
	return nil
}

func legacyPendingChoiceResult(
	proposal legacyPlanProposal,
) LegacyTransferChoiceResult {
	return LegacyTransferChoiceResult{
		Proposal:    proposal.identity,
		Occurrences: proposal.occurrences,
		Disposition: ChoicePending,
	}
}

func legacyDraftRetirementReady(
	plan LegacyTransferPlan,
	review LegacyTransferDraftReview,
) bool {
	return plan.SourceAccounting == AccountingComplete &&
		plan.ContentAccounting == AccountingComplete &&
		plan.MigrationReadiness != ReadinessBlocked &&
		review.PendingProposals == 0 &&
		review.SkippedProposals == 0
}

func validTransferSkipReason(reason TransferSkipReason) bool {
	switch reason {
	case TransferSkipDuplicate,
		TransferSkipObsolete,
		TransferSkipNotTransferable:
		return true
	default:
		return false
	}
}

func legacyProposalIdentityKey(identity LegacyProposalIdentity) string {
	parts := []string{
		string(identity.ComponentID),
		identity.ResourceID,
		string(identity.SourceRole),
		identity.ReferenceName,
	}
	parts = append(parts, identity.SectionPath...)
	var result strings.Builder
	for _, part := range parts {
		result.WriteString(strconv.Itoa(len(part)))
		result.WriteByte(':')
		result.WriteString(part)
	}
	return result.String()
}
