package tui

import (
	"fmt"
	"io"

	tea "charm.land/bubbletea/v2"
)

func Run(input io.Reader, output io.Writer, previewer Previewer) error {
	program := tea.NewProgram(
		NewModel(previewer),
		tea.WithInput(input),
		tea.WithOutput(output),
	)
	if _, err := program.Run(); err != nil {
		return fmt.Errorf("run terminal preview: %w", err)
	}
	return nil
}
