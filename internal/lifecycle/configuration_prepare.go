package lifecycle

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
)

func (service Service) PrepareConfiguration(
	request PreviewRequest,
) (configuration.PreparedPlan, error) {
	preview, err := service.Preview(request)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if len(preview.Configuration.Issues) > 0 ||
		len(preview.Configuration.ManualActions) > 0 ||
		preview.MCP.Blocking {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"configuration preview requires attention",
		)
	}
	generic := configuration.PreparedPlan{}
	if service.configurationInspection != nil {
		generic, err = service.configurationInspection.Prepare(
			service.configurationComponents(request.Components),
		)
		if err != nil {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"prepare configuration: %w",
				err,
			)
		}
	}
	if service.mcpInspection != nil {
		generic, err = service.mcpInspection.PrepareOnto(
			generic,
			request.Components,
			request.MCPSelections,
		)
		if err != nil {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"prepare MCP configuration: %w",
				err,
			)
		}
	}
	return generic, nil
}
