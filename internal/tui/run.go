package tui

import (
	"fmt"
	"io"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

func Run(
	input io.Reader,
	output io.Writer,
	previewer Previewer,
	catalog mcpcatalog.Catalog,
	stats mcpcatalog.StatsSource,
) error {
	program := tea.NewProgram(
		NewModel(previewer, catalog, stats),
		tea.WithInput(input),
		tea.WithOutput(output),
	)
	if _, err := program.Run(); err != nil {
		return fmt.Errorf("run terminal preview: %w", err)
	}
	return nil
}
