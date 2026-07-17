package mcpconfiguration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type baseMutationReference struct {
	transition int
	mutation   int
}

func newMCPPreparation(
	inspection Inspection,
	base configuration.PreparedPlan,
) *mcpPreparation {
	transitions := base.Transitions()
	builder := &mcpPreparation{
		inspection: inspection,
		base:       transitions,
		baseIndex:  make(map[domain.Location]baseMutationReference),
		baseAfter:  make(map[domain.Location][]byte),
		after:      make(map[domain.Location][]byte),
		touched:    make(map[domain.Location]bool),
		groups:     make(map[domain.Location]map[string]bool),
		registryOf: make(map[domain.Location]domain.Location),
	}
	for transitionIndex, transition := range transitions {
		for mutationIndex, mutation := range transition.Mutations {
			builder.baseIndex[mutation.Target] = baseMutationReference{
				transition: transitionIndex,
				mutation:   mutationIndex,
			}
		}
	}
	return builder
}

func (builder *mcpPreparation) useBaseAfter(
	target domain.Location,
) error {
	reference, exists := builder.baseIndex[target]
	if !exists {
		return nil
	}
	mutation := builder.base[reference.transition].Mutations[reference.mutation]
	snapshot, exists := builder.inspection.files[target]
	if !exists || snapshot.problem != "" || mutation.Before != mcpBeforeImage(snapshot) {
		return fmt.Errorf("base plan and MCP inspection before-images differ")
	}
	builder.baseAfter[target] = append([]byte(nil), mutation.After...)
	return nil
}

func (builder *mcpPreparation) rejectBaseMutation(
	target domain.Location,
) error {
	if _, exists := builder.baseIndex[target]; exists {
		return fmt.Errorf("base plan already mutates MCP registry target %v", target)
	}
	return nil
}

func (builder *mcpPreparation) mergeBaseTransition(
	configTarget domain.Location,
	mcp configuration.Transition,
) bool {
	reference, exists := builder.baseIndex[configTarget]
	_, verified := builder.baseAfter[configTarget]
	if !exists || !verified || !builder.touched[configTarget] {
		return false
	}
	base := &builder.base[reference.transition]
	for _, mutation := range mcp.Mutations {
		if mutation.Target == configTarget {
			base.Mutations[reference.mutation].After = append(
				[]byte(nil), mutation.After...,
			)
			continue
		}
		base.Mutations = append(base.Mutations, mutation)
	}
	base.ResourceIDs = append(base.ResourceIDs, mcp.ResourceIDs...)
	return true
}
