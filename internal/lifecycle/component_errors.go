package lifecycle

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

// Component is safe to disclose in user-facing output: it is proven to belong
// to the selectable set before this error can be produced.
type ComponentHostRequirementError struct {
	Component domain.ComponentID
}

func (err ComponentHostRequirementError) Error() string {
	return fmt.Sprintf(
		"component %q does not satisfy its host requirement",
		err.Component,
	)
}
