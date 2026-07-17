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
	existingPresent    bool
	existingComparable bool
	existingRaw        string
	ownedPresent       bool
	ownedTombstone     bool
	ownedRaw           string
	configProblem      string
	registryProblem    string
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
	existing := inspectTargetEntry(projection, host)
	registry, registryMissing, registryProblem := inspectDocument(
		projection.RegistryTarget,
		host,
	)
	snapshot := projectionSnapshot{
		existingPresent:    existing.present,
		existingComparable: existing.comparable,
		existingRaw:        existing.raw,
		configProblem:      existing.problem,
		registryProblem:    registryProblem,
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

type targetEntryObservation struct {
	present    bool
	comparable bool
	raw        string
	problem    string
}

func inspectTargetEntry(
	projection releasecontract.MCPProjection,
	host Host,
) targetEntryObservation {
	entry, err := host.Inspect(projection.Target, true)
	if errors.Is(err, fs.ErrNotExist) {
		return targetEntryObservation{comparable: true}
	}
	if err != nil {
		return targetEntryObservation{problem: "configuration inspection failed"}
	}
	if entry.Kind == hostfs.EntrySymlink {
		return targetEntryObservation{problem: "configuration target is a symbolic link"}
	}
	if entry.Kind != hostfs.EntryRegular {
		return targetEntryObservation{problem: "configuration target is not a regular file"}
	}
	pointer, err := jsondocument.ParsePointer(
		projection.MapPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return targetEntryObservation{problem: "MCP projection pointer is invalid"}
	}
	return lookupTargetEntry(projection.TargetDocumentFormat(), entry.Content, pointer)
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
