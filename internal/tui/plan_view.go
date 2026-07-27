package tui

import "github.com/CATWILLgh/MAINFRAME/internal/domain"

func operationsByKind(
	operations []domain.Operation,
	kind domain.OperationKind,
) []domain.Operation {
	filtered := make([]domain.Operation, 0)
	for _, operation := range operations {
		if operation.Kind == kind {
			filtered = append(filtered, operation)
		}
	}
	return filtered
}
