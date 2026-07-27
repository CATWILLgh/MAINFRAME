package tui

import "strings"

func (model *Model) previewView() string {
	sections := []string{header()}
	sections = append(sections, model.reviewedPlanSections()...)
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	footer := "b back  •  q quit"
	if plan, ok := model.reviewedPlan.(applicableReviewedPlan); ok &&
		plan.Applicable() {
		footer = "a review and apply  •  " + footer
	} else {
		sections = append(sections, mutedStyle.Render(
			"Preview only. No safe apply action is available for this plan.",
		))
	}
	sections = append(sections, mutedStyle.Render(footer))
	return strings.Join(sections, "\n\n")
}
