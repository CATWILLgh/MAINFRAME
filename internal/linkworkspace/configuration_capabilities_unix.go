//go:build darwin || linux

package linkworkspace

import (
	"errors"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

func (workspace Workspace) CheckConfigurationCapabilities(
	mutation executor.JournalConfigurationMutation,
) error {
	context, err := workspace.openConfigurationMutation(mutation)
	if err != nil {
		return err
	}
	defer context.close()
	if err := checkConfigurationFilesystem(context.parentFD); err != nil {
		return err
	}
	if err := probeConfigurationRenames(context.privateFD); err != nil {
		return err
	}
	return errors.Join(
		syncDirectory(context.parentFD),
		syncDirectory(context.privateFD),
	)
}
