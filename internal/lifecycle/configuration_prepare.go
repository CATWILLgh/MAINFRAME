package lifecycle

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/diagnostics"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (service Service) PrepareConfiguration(
	request PreviewRequest,
) (configuration.PreparedPlan, error) {
	preservationRoots := service.preservationRoots(request.Components)
	preview, err := service.Preview(request)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if err := validateConfigurationPreview(preview); err != nil {
		return configuration.PreparedPlan{}, err
	}
	base, err := service.prepareBaseConfiguration(request, preservationRoots)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if len(preview.Diagnostics.Intents) == 0 {
		return base, nil
	}
	exact, err := service.prepareDiagnosticsConfiguration(preview.Diagnostics)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	combined, err := configuration.CombinePreparedPlans(base, exact)
	if err != nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"combine diagnostics configuration: %w",
			err,
		)
	}
	return combined, nil
}

func validateConfigurationPreview(preview Preview) error {
	if len(preview.Configuration.Issues) > 0 ||
		len(preview.Configuration.ManualActions) > 0 ||
		preview.MCP.Blocking {
		return fmt.Errorf("configuration preview requires attention")
	}
	if len(preview.Diagnostics.Intents) > 0 &&
		!preview.Diagnostics.Executable {
		return fmt.Errorf("scoped diagnostics resource is unavailable")
	}
	return nil
}

func (service Service) prepareBaseConfiguration(
	request PreviewRequest,
	preservationRoots []domain.ComponentID,
) (configuration.PreparedPlan, error) {
	prepared := configuration.PreparedPlan{}
	var err error
	if service.configurationInspection != nil {
		prepared, err = service.configurationInspection.PrepareWithPreservation(
			service.configurationComponents(request.Components),
			service.configurationComponents(preservationRoots),
		)
		if err != nil {
			return configuration.PreparedPlan{}, fmt.Errorf(
				"prepare configuration: %w",
				err,
			)
		}
	}
	if service.mcpInspection == nil {
		return prepared, nil
	}
	prepared, err = service.mcpInspection.PrepareOntoWithPreservation(
		prepared,
		request.Components,
		preservationRoots,
		request.MCPSelections,
	)
	if err != nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"prepare MCP configuration: %w",
			err,
		)
	}
	return prepared, nil
}

func (service Service) prepareDiagnosticsConfiguration(
	plan diagnostics.Plan,
) (configuration.PreparedPlan, error) {
	if service.configurationInspection == nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"scoped diagnostics resource is unavailable",
		)
	}
	documents, available, err := diagnosticsExactDocuments(
		plan,
		service.configurationInspection.Resources(),
	)
	if err != nil {
		return configuration.PreparedPlan{}, err
	}
	if !available {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"scoped diagnostics resource is unavailable",
		)
	}
	prepared, err := service.configurationInspection.PrepareExactJSONDocuments(
		documents,
	)
	if err != nil {
		return configuration.PreparedPlan{}, fmt.Errorf(
			"prepare diagnostics configuration: %w",
			err,
		)
	}
	return prepared, nil
}
