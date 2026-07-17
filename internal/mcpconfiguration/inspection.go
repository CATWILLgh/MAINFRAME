package mcpconfiguration

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

type Host interface {
	Inspect(domain.Location, bool) (hostfs.Entry, error)
}

type Inspection struct {
	projections []releasecontract.MCPProjection
	catalog     mcpcatalog.Catalog
	snapshots   map[string]projectionSnapshot
}

type projectionSnapshot struct {
	existingPresent bool
	existingRaw     string
	ownedPresent    bool
	ownedTombstone  bool
	ownedRaw        string
	configProblem   string
	registryProblem string
}

func Inspect(
	projections []releasecontract.MCPProjection,
	catalog mcpcatalog.Catalog,
	host Host,
) (Inspection, error) {
	if host == nil {
		return Inspection{}, fmt.Errorf("host must not be nil")
	}
	if err := releasecontract.ValidateMCPProjections(projections, catalog); err != nil {
		return Inspection{}, fmt.Errorf("validate MCP projections: %w", err)
	}
	cloned := append([]releasecontract.MCPProjection(nil), projections...)
	inspection := Inspection{
		projections: cloned,
		catalog:     catalog,
		snapshots:   make(map[string]projectionSnapshot, len(cloned)),
	}
	for _, projection := range cloned {
		inspection.snapshots[projection.ID] = inspectProjection(projection, host)
	}
	return inspection, nil
}

func inspectProjection(
	projection releasecontract.MCPProjection,
	host Host,
) projectionSnapshot {
	config, configMissing, configProblem := inspectDocument(projection.Target, host)
	registry, registryMissing, registryProblem := inspectDocument(
		projection.RegistryTarget,
		host,
	)
	snapshot := projectionSnapshot{
		configProblem:   configProblem,
		registryProblem: registryProblem,
	}
	if !configMissing && configProblem == "" {
		pointer, err := jsondocument.ParsePointer(
			projection.MapPointer + "/" + projection.EntryKey,
		)
		if err != nil {
			snapshot.configProblem = "MCP projection pointer is invalid"
			return snapshot
		}
		raw, status := config.Lookup(pointer)
		switch status {
		case jsondocument.Found:
			snapshot.existingPresent, snapshot.existingRaw = true, raw
		case jsondocument.Incompatible:
			snapshot.configProblem = "configuration MCP map is not an object"
		}
	}
	if registryMissing || registryProblem != "" {
		return snapshot
	}
	owned, tombstone, present, err := registryEntry(registry, projection)
	if err != nil {
		snapshot.registryProblem = err.Error()
		return snapshot
	}
	snapshot.ownedRaw = owned
	snapshot.ownedTombstone = tombstone
	snapshot.ownedPresent = present
	return snapshot
}

func inspectDocument(
	location domain.Location,
	host Host,
) (jsondocument.Document, bool, string) {
	entry, err := host.Inspect(location, true)
	if errors.Is(err, fs.ErrNotExist) {
		return jsondocument.Document{}, true, ""
	}
	if err != nil {
		return jsondocument.Document{}, false, "configuration inspection failed"
	}
	switch entry.Kind {
	case hostfs.EntrySymlink:
		return jsondocument.Document{}, false, "configuration target is a symbolic link"
	case hostfs.EntryRegular:
		document, err := jsondocument.Parse(entry.Content)
		if err != nil {
			return jsondocument.Document{}, false, "configuration JSON is invalid"
		}
		return document, false, ""
	default:
		return jsondocument.Document{}, false, "configuration target is not a regular file"
	}
}

func registryEntry(
	document jsondocument.Document,
	projection releasecontract.MCPProjection,
) (string, bool, bool, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal([]byte(document.Canonical()), &root); err != nil ||
		len(root) != 2 || string(root["version"]) != "1" || root["servers"] == nil {
		return "", false, false, fmt.Errorf("MCP ownership registry is invalid")
	}
	pointer, err := jsondocument.ParsePointer(
		projection.RegistryEntriesPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return "", false, false, fmt.Errorf("MCP registry pointer is invalid")
	}
	raw, status := document.Lookup(pointer)
	if status == jsondocument.Missing {
		return "", false, false, nil
	}
	if status != jsondocument.Found {
		return "", false, false, fmt.Errorf("MCP ownership registry entries are invalid")
	}
	if raw == "null" {
		return "", true, true, nil
	}
	var object map[string]any
	if err := json.Unmarshal([]byte(raw), &object); err != nil || object == nil {
		return "", false, false, fmt.Errorf("MCP ownership registry entry is invalid")
	}
	return raw, false, true, nil
}
