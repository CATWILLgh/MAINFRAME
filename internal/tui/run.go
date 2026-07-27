package tui

import (
	"fmt"
	"io"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type CredentialState struct {
	Definitions credentialcatalog.Definitions
	Instances   credentialcatalog.Instances
}

func Run(
	input io.Reader,
	output io.Writer,
	reviewer PlanReviewer,
	catalog mcpcatalog.Catalog,
	stats mcpcatalog.StatsSource,
	credentials CredentialState,
) error {
	program := tea.NewProgram(
		NewModel(reviewer, catalog, stats, credentials),
		tea.WithInput(input),
		tea.WithOutput(output),
	)
	if _, err := program.Run(); err != nil {
		return fmt.Errorf("run terminal preview: %w", err)
	}
	return nil
}
