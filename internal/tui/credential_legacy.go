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
	model.form = huh.NewForm(huh.NewGroup(
		huh.NewSelect[credentialMenuChoice]().
			Title("Legacy credential locations").
			Options(huh.NewOption("Back to credentials", credentialBack)).
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
