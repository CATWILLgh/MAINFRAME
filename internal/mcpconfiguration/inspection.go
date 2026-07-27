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
	files       map[domain.Location]mcpFileSnapshot
	migrations  map[domain.ComponentID]migrationSnapshot
}

type projectionSnapshot struct {
	existingPresent     bool
	existingComparable  bool
	existingRaw         string
	ownedPresent        bool
	ownedTombstone      bool
	ownedMaterializable bool
	ownedRaw            string
	configProblem       string
	registryProblem     string
}

type mcpFileSnapshot struct {
	kind              hostfs.EntryKind
	path              string
	symlinkTargetPath string
	present           bool
	raw               []byte
	mode              uint32
	device            uint64
	inode             uint64
	birthSeconds      int64
	birthNanoseconds  int64
	problem           string
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
		files:       make(map[domain.Location]mcpFileSnapshot),
		migrations:  make(map[domain.ComponentID]migrationSnapshot),
	}
	for _, projection := range cloned {
		inspection.captureFile(projection.Target, host)
		inspection.captureFile(projection.RegistryTarget, host)
		inspection.snapshots[projection.ID] = inspection.inspectProjection(projection)
	}
	inspection.captureAntigravityMigration(cloned, host)
	return inspection, nil
}

func (inspection *Inspection) captureFile(location domain.Location, host Host) {
	if _, exists := inspection.files[location]; exists {
		return
	}
	entry, err := host.Inspect(location, true)
	if errors.Is(err, fs.ErrNotExist) {
		inspection.files[location] = mcpFileSnapshot{}
		return
	}
	if err != nil {
		inspection.files[location] = mcpFileSnapshot{problem: "configuration inspection failed"}
		return
	}
	snapshot := mcpFileSnapshot{
		kind: entry.Kind, path: entry.Path, symlinkTargetPath: entry.SymlinkTargetPath,
		mode: entry.Mode, device: entry.Device, inode: entry.Inode,
		birthSeconds:     entry.BirthSeconds,
		birthNanoseconds: entry.BirthNanoseconds,
	}
	switch entry.Kind {
	case hostfs.EntrySymlink:
		snapshot.problem = "configuration target is a symbolic link"
	case hostfs.EntryRegular:
		snapshot.present = true
		snapshot.raw = append([]byte(nil), entry.Content...)
	default:
		snapshot.problem = "configuration target is not a regular file"
	}
	inspection.files[location] = snapshot
}

func (inspection Inspection) inspectProjection(
	projection releasecontract.MCPProjection,
) projectionSnapshot {
	existing := inspectTargetEntry(projection, inspection.files[projection.Target])
	registry, registryMissing, registryProblem := inspectDocument(
		inspection.files[projection.RegistryTarget],
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
	owned, tombstone, present, materializable, err := registryEntry(registry, projection)
	if err != nil {
		snapshot.registryProblem = err.Error()
		return snapshot
	}
	snapshot.ownedRaw = owned
	snapshot.ownedTombstone = tombstone
	snapshot.ownedPresent = present
	snapshot.ownedMaterializable = materializable
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
	file mcpFileSnapshot,
) targetEntryObservation {
	if file.problem != "" {
		return targetEntryObservation{problem: file.problem}
	}
	if !file.present {
		return targetEntryObservation{comparable: true}
	}
	pointer, err := jsondocument.ParsePointer(
		projection.MapPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return targetEntryObservation{problem: "MCP projection pointer is invalid"}
	}
	return lookupTargetEntry(projection.TargetDocumentFormat(), file.raw, pointer)
}

func inspectDocument(
	file mcpFileSnapshot,
) (jsondocument.Document, bool, string) {
	if file.problem != "" {
		return jsondocument.Document{}, false, file.problem
	}
	if !file.present {
		return jsondocument.Document{}, true, ""
	}
	document, err := jsondocument.Parse(file.raw)
	if err != nil {
		return jsondocument.Document{}, false, "configuration JSON is invalid"
	}
	return document, false, ""
}

func registryEntry(
	document jsondocument.Document,
	projection releasecontract.MCPProjection,
) (string, bool, bool, bool, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal([]byte(document.Canonical()), &root); err != nil ||
		len(root) != 2 || string(root["version"]) != "1" || root["servers"] == nil {
		return "", false, false, false, fmt.Errorf("MCP ownership registry is invalid")
	}
	pointer, err := jsondocument.ParsePointer(
		projection.RegistryEntriesPointer + "/" + projection.EntryKey,
	)
	if err != nil {
		return "", false, false, false, fmt.Errorf("MCP registry pointer is invalid")
	}
	raw, status := document.Lookup(pointer)
	if status == jsondocument.Missing {
		return "", false, false, false, nil
	}
	if status != jsondocument.Found {
		return "", false, false, false, fmt.Errorf("MCP ownership registry entries are invalid")
	}
	if raw == "null" {
		return "", true, true, true, nil
	}
	var object map[string]any
	if err := json.Unmarshal([]byte(raw), &object); err != nil || object == nil {
		return "", false, false, false, fmt.Errorf("MCP ownership registry entry is invalid")
	}
	if projection.TargetDocumentFormat() != releasecontract.MCPProjectionDocumentTOML {
		return raw, false, true, true, nil
	}
	entry, materializable, err := decodeCodexRegistryEntry([]byte(raw))
	if err != nil {
		return "", false, false, false, err
	}
	if materializable {
		return entry, false, true, true, nil
	}
	return raw, false, true, false, nil
}
