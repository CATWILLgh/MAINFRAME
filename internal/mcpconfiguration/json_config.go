package mcpconfiguration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func (builder *mcpPreparation) materializeJSONConfig(
	projection releasecontract.MCPProjection,
	intent Intent,
) ([]byte, error) {
	if err := builder.useBaseAfter(projection.Target); err != nil {
		return nil, err
	}
	raw := builder.current(projection.Target)
	_, hasBaseAfter := builder.baseAfter[projection.Target]
	if !builder.inspection.files[projection.Target].present &&
		!hasBaseAfter && !builder.touched[projection.Target] {
		raw = []byte(`{}`)
	}
	document, err := jsondocument.Parse(raw)
	if err != nil {
		return nil, fmt.Errorf("parse JSON MCP configuration: %w", err)
	}
	pointer, err := jsondocument.ParsePointer(
		projection.MapPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return nil, err
	}
	switch intent.Kind {
	case IntentAdd, IntentUpdate:
		document, err = document.Set(pointer, []byte(projection.DesiredEntry))
	case IntentRemove:
		document, err = document.Delete(pointer)
	case IntentConflict, IntentUnsupported:
		return nil, fmt.Errorf("MCP intent %q cannot be materialized", intent.Kind)
	default:
		return nil, fmt.Errorf("unsupported MCP intent %q", intent.Kind)
	}
	if err != nil {
		return nil, fmt.Errorf("materialize JSON MCP configuration: %w", err)
	}
	return document.Indented(), nil
}
