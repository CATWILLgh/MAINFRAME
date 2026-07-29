package tui

import (
	"fmt"
	"strings"
)

func (model *Model) legacyTransferDraftActionView() string {
	proposal, _ := model.legacyTransferProposal(
		model.activeLegacyDraftProposal,
	)
	return strings.Join([]string{
		headingStyle.Render("MAINFRAME"),
		headingStyle.Render("Account for " + proposal.ReferenceName),
		bannerStyle.Render("Draft only. Secret values are never read."),
		model.form.View(),
		mutedStyle.Render("enter choose  •  b back  •  q quit"),
	}, "\n\n")
}

func (model *Model) legacyTransferDraftCreateView() string {
	service, _ := model.credentialDefinitions.Service(
		model.legacyTransferInstanceDraft.serviceID,
	)
	sections := []string{
		headingStyle.Render("MAINFRAME"),
		headingStyle.Render("Draft " + service.Name + " instance"),
		bannerStyle.Render(
			"Stored only in this transfer draft. Nothing is written.",
		),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(
		sections,
		mutedStyle.Render("enter continue  •  esc cancel  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}

func (model *Model) legacyTransferDraftReviewView() string {
	review := model.legacyTransferDraftReview
	retirement := "Legacy locations are not ready for retirement."
	if review.RetirementReady {
		retirement = "Draft accounting is complete, but retirement is not authorized here."
	}
	sections := []string{
		headingStyle.Render("MAINFRAME"),
		headingStyle.Render("Transfer draft review"),
		bannerStyle.Render("Inspection only. Nothing has been written."),
		fmt.Sprintf(
			"%d transferred; %d skipped; %d pending.",
			review.TransferredProposals,
			review.SkippedProposals,
			review.PendingProposals,
		),
		retirement,
	}
	if review.ManualContentReviewRequired {
		sections = append(
			sections,
			"Manual content review is still required.",
		)
	}
	sections = append(
		sections,
		model.form.View(),
		mutedStyle.Render("enter or b back  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}
