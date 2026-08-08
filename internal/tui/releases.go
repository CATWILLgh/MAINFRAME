package tui

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
)

const (
	releaseMenuBack   releaseMenuChoice = ":back"
	releaseMenuImport releaseMenuChoice = ":import"
)

func (model *Model) openReleases() (*Model, tea.Cmd) {
	model.screen = screenReleases
	model.err = nil
	model.releaseApplied = false
	model.releaseAppliedNotice = ""
	model.activeReleaseReview = nil
	if model.releases.Lister == nil {
		model.releaseList = nil
		model.form = releaseMenuForm(model, nil)
		return model, model.form.Init()
	}
	entries, err := model.releases.Lister.List()
	if err != nil {
		model.err = err
		model.releaseList = nil
		model.form = releaseMenuForm(model, nil)
		return model, model.form.Init()
	}
	model.releaseList = entries
	model.releaseMenuChoice = releaseMenuBack
	model.form = releaseMenuForm(model, entries)
	return model, model.form.Init()
}

func releaseMenuForm(model *Model, entries []ReleaseSummary) *huh.Form {
	options := make([]huh.Option[releaseMenuChoice], 0, len(entries)+2)
	for _, entry := range entries {
		label := fmt.Sprintf(
			"%s (%s)",
			entry.ReleaseID,
			shortSHA(entry.IndexSHA256),
		)
		if entry.Active {
			label = label + "  [active]"
		}
		value := releaseMenuChoice(
			"activate:" + entry.ReleaseID + ":" + entry.IndexSHA256,
		)
		options = append(options, huh.NewOption(label, value))
	}
	if model.releases.Reviewer != nil {
		options = append(options, huh.NewOption(
			"Import from path…", releaseMenuImport,
		))
	}
	options = append(options, huh.NewOption("Back to overview", releaseMenuBack))
	field := huh.NewSelect[releaseMenuChoice]().
		Title("Choose a release").
		Options(options...).
		Value(&model.releaseMenuChoice)
	return huh.NewForm(huh.NewGroup(field)).WithShowHelp(false)
}

func (model *Model) continueFromReleases() (*Model, tea.Cmd) {
	if model.releaseMenuChoice == releaseMenuBack {
		return model.openMain()
	}
	if model.releaseMenuChoice == releaseMenuImport {
		return model.openReleaseImport()
	}
	value := string(model.releaseMenuChoice)
	if strings.HasPrefix(value, "activate:") {
		rest := strings.TrimPrefix(value, "activate:")
		parts := strings.SplitN(rest, ":", 2)
		if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
			model.err = fmt.Errorf("Selected release identity is malformed")
			return model.openReleases()
		}
		return model.openReleaseConfirmCached(parts[0], parts[1])
	}
	model.err = fmt.Errorf("Selected release action is unavailable")
	return model.openReleases()
}

func (model *Model) openReleaseImport() (*Model, tea.Cmd) {
	model.screen = screenReleaseImport
	model.err = nil
	model.releaseImportPath = ""
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewInput().
			Title("Absolute path to a local release").
			Description("Built by tools/build_release.py — reviewed and applied as one transaction.").
			Value(&model.releaseImportPath),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) continueFromReleaseImport() (*Model, tea.Cmd) {
	if model.releases.Reviewer == nil {
		model.err = fmt.Errorf("Release review is unavailable")
		return model.openReleases()
	}
	path := strings.TrimSpace(model.releaseImportPath)
	if path == "" {
		return model.openReleases()
	}
	review, err := model.releases.Reviewer.ReviewImport(path)
	if err != nil {
		model.err = err
		return model.openReleases()
	}
	return model.showReleaseReview(review)
}

func (model *Model) openReleaseConfirmCached(
	releaseID, indexSHA256 string,
) (*Model, tea.Cmd) {
	if model.releases.Reviewer == nil {
		model.err = fmt.Errorf("Release review is unavailable")
		return model.openReleases()
	}
	review, err := model.releases.Reviewer.ReviewActivateCached(releaseID, indexSHA256)
	if err != nil {
		model.err = err
		return model.openReleases()
	}
	return model.showReleaseReview(review)
}

func (model *Model) showReleaseReview(review ReleaseReview) (*Model, tea.Cmd) {
	stored := review
	model.activeReleaseReview = &stored
	model.screen = screenReleaseConfirm
	model.releaseApplied = false
	model.releaseAppliedNotice = ""
	model.applyConfirmed = false
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Apply this release activation now?").
			Description("The running binary keeps its inode; restart MAINFRAME to use the new version.").
			Value(&model.applyConfirmed),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) continueFromReleaseConfirm() (*Model, tea.Cmd) {
	if model.activeReleaseReview == nil {
		return model.openReleases()
	}
	if !model.applyConfirmed {
		model.screen = screenReleases
		model.form = releaseMenuForm(model, model.releaseList)
		return model, model.form.Init()
	}
	if model.releases.Applier == nil {
		model.err = fmt.Errorf("Release apply is unavailable")
		model.screen = screenReleases
		model.form = releaseMenuForm(model, model.releaseList)
		return model, model.form.Init()
	}
	if err := model.releases.Applier.Apply(*model.activeReleaseReview); err != nil {
		model.err = err
		model.screen = screenReleases
		model.form = releaseMenuForm(model, model.releaseList)
		return model, model.form.Init()
	}
	model.releaseApplied = true
	model.releaseAppliedNotice = "Release activated. Restart MAINFRAME to run the new version."
	model.err = nil
	model.screen = screenReleases
	model.releaseList = markActiveRelease(model.releaseList, *model.activeReleaseReview)
	model.form = releaseMenuForm(model, model.releaseList)
	return model, model.form.Init()
}

func markActiveRelease(
	entries []ReleaseSummary, review ReleaseReview,
) []ReleaseSummary {
	updated := make([]ReleaseSummary, len(entries))
	for index, entry := range entries {
		entry.Active = entry.ReleaseID == review.Target.ReleaseID &&
			entry.IndexSHA256 == review.Target.IndexSHA256
		updated[index] = entry
	}
	return updated
}

func (model *Model) releasesView() string {
	sections := []string{
		header(),
		headingStyle.Render("Releases"),
	}
	if model.releases.Lister == nil {
		sections = append(sections, mutedStyle.Render(
			"Release management is unavailable in this session.",
		))
	} else if len(model.releaseList) == 0 && model.err == nil {
		sections = append(sections, mutedStyle.Render(
			"No cached releases. Import one from a path below.",
		))
		sections = append(sections, model.form.View())
	} else {
		sections = append(sections, model.form.View())
	}
	if model.releaseAppliedNotice != "" {
		sections = append(sections, bannerStyle.Render(model.releaseAppliedNotice))
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render(
		"enter open  •  b back  •  q quit",
	))
	return strings.Join(sections, "\n\n")
}

func (model *Model) releaseImportView() string {
	sections := []string{
		header(),
		headingStyle.Render("Import release from path"),
		model.form.View(),
	}
	if model.err != nil {
		sections = append(sections, errorStyle.Render(model.err.Error()))
	}
	sections = append(sections, mutedStyle.Render(
		"enter review  •  b back  •  q quit",
	))
	return strings.Join(sections, "\n\n")
}

func (model *Model) releaseConfirmView() string {
	sections := []string{
		header(),
		headingStyle.Render("Review release activation"),
	}
	if model.activeReleaseReview != nil {
		sections = append(sections, releaseReviewSections(*model.activeReleaseReview)...)
	}
	if model.releaseAppliedNotice != "" {
		sections = append(sections, bannerStyle.Render(model.releaseAppliedNotice))
	}
	sections = append(sections,
		model.form.View(),
		mutedStyle.Render("enter confirm  •  b back  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}

func releaseReviewSections(review ReleaseReview) []string {
	lines := []string{
		fmt.Sprintf(
			"Target:   %s (%s)",
			review.Target.ReleaseID, shortSHA(review.Target.IndexSHA256),
		),
	}
	if review.Previous != nil {
		lines = append(lines, fmt.Sprintf(
			"Previous: %s (%s)",
			review.Previous.ReleaseID, shortSHA(review.Previous.IndexSHA256),
		))
	}
	if review.RecoveryRequired {
		lines = append(lines, "Recovery required: an unfinished transaction must be resolved first (use the CLI).")
	} else if review.Applicable {
		lines = append(lines, "Applicable: yes")
	} else {
		lines = append(lines, "Applicable: no (review only)")
	}
	for _, operation := range review.Operations {
		lines = append(lines, fmt.Sprintf(
			"  %s  %s", operation.Kind, operation.ComponentID,
		))
	}
	for _, notice := range review.Notices {
		lines = append(lines, mutedStyle.Render(notice))
	}
	sections := make([]string, 0, len(lines))
	for _, line := range lines {
		sections = append(sections, line)
	}
	return sections
}

func shortSHA(sha string) string {
	if len(sha) <= 12 {
		return sha
	}
	return sha[:12]
}
