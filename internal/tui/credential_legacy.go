package tui

import (
	"errors"
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
)

func (model *Model) openLegacyCredentialIndexes() (*Model, tea.Cmd) {
	indexes, err := model.legacyCredentialInspector.Inspect()
	if err != nil {
		updated, command := model.openCredentials()
		updated.err = errors.New(
			"Legacy credential locations could not be inspected safely",
		)
		return updated, command
	}
	model.legacyCredentialIndexes = append(
		[]credentialmigration.LegacyIndex(nil),
		indexes...,
	)
	model.screen = screenCredentialLegacy
	model.err = nil
	model.credentialMenuChoice = credentialBack
	options := make([]huh.Option[credentialMenuChoice], 0, 2)
	if model.legacyCredentialPreviewer != nil {
		options = append(options, huh.NewOption(
			"Discover named references in the shared catalog",
			credentialLegacyPreview,
		))
	}
	options = append(options, huh.NewOption(
		"Back to credentials",
		credentialBack,
	))
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Legacy credential locations").
			Options(options...).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) continueFromLegacyCredentials() (*Model, tea.Cmd) {
	if model.credentialMenuChoice == credentialLegacyPreview {
		return model.openLegacyCredentialReferencePreview()
	}
	return model.openCredentials()
}

func (model *Model) openLegacyCredentialReferencePreview() (*Model, tea.Cmd) {
	if model.legacyCredentialPreviewer == nil {
		updated, command := model.openLegacyCredentialIndexes()
		updated.err = errors.New("Named-reference discovery is unavailable")
		return updated, command
	}
	preview, err := model.legacyCredentialPreviewer.Preview()
	if err != nil {
		updated, command := model.openLegacyCredentialIndexes()
		updated.err = errors.New(
			"Named references could not be previewed safely",
		)
		return updated, command
	}
	model.legacyCredentialReferencePreview = preview
	return model.openLegacyReferencePreviewMenu()
}

func (model *Model) openLegacyReferencePreviewMenu() (*Model, tea.Cmd) {
	model.screen = screenCredentialLegacyPreview
	model.err = nil
	model.credentialMenuChoice = credentialBack
	options := make([]huh.Option[credentialMenuChoice], 0)
	for index, group := range model.legacyCredentialReferencePreview.References.Groups {
		label := strings.Join(group.SectionPath, " / ") +
			" — " + referenceCountText(len(group.References))
		options = append(options, huh.NewOption(
			label,
			credentialMenuChoice(fmt.Sprintf("legacy-group:%d", index)),
		))
	}
	options = append(options, huh.NewOption(
		"Back to legacy locations",
		credentialBack,
	))
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Named-reference groups").
			Options(options...).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) continueFromLegacyReferencePreview() (*Model, tea.Cmd) {
	value := string(model.credentialMenuChoice)
	if model.credentialMenuChoice == credentialBack {
		model.clearLegacyReferencePreview()
		return model.openLegacyCredentialIndexes()
	}
	var index int
	if _, err := fmt.Sscanf(value, "legacy-group:%d", &index); err != nil {
		model.err = errors.New("Selected reference group is unavailable")
		return model.openLegacyReferencePreviewMenu()
	}
	return model.openLegacyReferenceGroup(index)
}

func (model *Model) openLegacyReferenceGroup(index int) (*Model, tea.Cmd) {
	groups := model.legacyCredentialReferencePreview.References.Groups
	if index < 0 || index >= len(groups) {
		model.err = errors.New("Selected reference group is unavailable")
		return model.openLegacyReferencePreviewMenu()
	}
	model.activeLegacyReferenceGroup = index
	model.screen = screenCredentialLegacyGroup
	model.err = nil
	model.credentialMenuChoice = credentialBack
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Reference details").
			Options(huh.NewOption(
				"Back to named-reference groups",
				credentialBack,
			)).
			Value(&model.credentialMenuChoice),
	)).WithShowHelp(false)
	return model, model.form.Init()
}

func (model *Model) legacyCredentialIndexesView() string {
	lines := make([]string, 0, len(model.legacyCredentialIndexes))
	for _, index := range model.legacyCredentialIndexes {
		lines = append(lines, fmt.Sprintf(
			"• %s — %s; %s",
			componentName(index.ComponentID),
			legacyCredentialSourceRoleText(index),
			legacyCredentialStateText(index),
		))
	}
	sections := []string{
		header(),
		headingStyle.Render("Legacy credential locations"),
		bannerStyle.Render(
			"Old files stay unchanged — readiness only.",
		),
		"MAINFRAME will not write, delete, or adopt these files.",
		strings.Join(lines, "\n"),
		model.form.View(),
		mutedStyle.Render("enter or b back  •  q quit"),
	}
	return strings.Join(sections, "\n\n")
}

func (model *Model) legacyCredentialReferencePreviewView() string {
	references := model.legacyCredentialReferencePreview.References
	sections := []string{
		header(),
		headingStyle.Render("Partial named-reference discovery"),
		bannerStyle.Render(
			"This is a review aid, not a completed migration.",
		),
		fmt.Sprintf(
			"%d named uses found; %d mentions excluded; %d description lines still need manual review.",
			references.ExtractedReferenceMentions,
			references.ExcludedReferenceMentions,
			references.UnmappedContentLines,
		),
	}
	if pendingLegacySources(model.legacyCredentialReferencePreview.Indexes) > 0 {
		sections = append(sections, mutedStyle.Render(
			"Divergent or blocked adapter copies still need separate review.",
		))
	}
	sections = append(
		sections,
		model.form.View(),
		mutedStyle.Render("enter inspect  •  b back  •  q quit"),
	)
	return strings.Join(sections, "\n\n")
}

func (model *Model) legacyCredentialReferenceGroupView() string {
	group := model.legacyCredentialReferencePreview.
		References.Groups[model.activeLegacyReferenceGroup]
	lines := make([]string, len(group.References))
	for index, reference := range group.References {
		lines[index] = fmt.Sprintf(
			"• %s — %s; %s",
			reference.Name,
			referenceCompatibilityText(reference.Compatibility),
			occurrenceCountText(reference.Occurrences),
		)
	}
	sections := []string{
		header(),
		headingStyle.Render(strings.Join(group.SectionPath, " / ")),
		bannerStyle.Render(
			"Names only. Values were not read.",
		),
		strings.Join(lines, "\n"),
		model.form.View(),
		mutedStyle.Render("enter or b back  •  q quit"),
	}
	return strings.Join(sections, "\n\n")
}

func (model *Model) clearLegacyReferencePreview() {
	model.legacyCredentialReferencePreview =
		credentialmigration.LegacyReferenceInventory{}
	model.activeLegacyReferenceGroup = 0
}

func pendingLegacySources(indexes []credentialmigration.LegacyIndex) int {
	count := 0
	for _, index := range indexes {
		if index.SourceRole == credentialmigration.SourceRoleAdapterCopy &&
			index.MigrationReadiness !=
				credentialmigration.ReadinessNoTransferRequired {
			count++
		}
	}
	return count
}

func referenceCountText(count int) string {
	if count == 1 {
		return "1 reference"
	}
	return fmt.Sprintf("%d references", count)
}

func occurrenceCountText(count int) string {
	if count == 1 {
		return "1 occurrence"
	}
	return fmt.Sprintf("%d occurrences", count)
}

func referenceCompatibilityText(
	compatibility credentialmigration.ReferenceCompatibility,
) string {
	if compatibility == credentialmigration.ReferenceCatalogCompatible {
		return "catalog compatible"
	}
	return "legacy name; rename is required before transfer"
}

func legacyCredentialSourceRoleText(
	index credentialmigration.LegacyIndex,
) string {
	switch index.SourceRole {
	case credentialmigration.SourceRoleSharedOriginal:
		return "original shared catalog location"
	case credentialmigration.SourceRoleAdapterCopy:
		return "defensive check for a later adapter copy"
	default:
		return "historical source role unavailable"
	}
}

func legacyCredentialStateText(
	index credentialmigration.LegacyIndex,
) string {
	switch index.MigrationReadiness {
	case credentialmigration.ReadinessNoTransferRequired:
		if index.SourceRole == credentialmigration.SourceRoleAdapterCopy &&
			index.State == credentialmigration.IndexMissing {
			return "missing adapter copies are normal; no transfer is required"
		}
		return "no transfer is required"
	case credentialmigration.ReadinessManualTransferRequired:
		return "manual transfer is required; the old file stays unchanged"
	case credentialmigration.ReadinessBlocked:
		return "needs attention before transfer; the old file stays unchanged"
	default:
		return "readiness is unavailable; the old file stays unchanged"
	}
}
