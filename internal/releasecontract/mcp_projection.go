package releasecontract

import (
	"encoding/json"
	"fmt"
	"sort"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const (
	openCodeMCPMapPointer      = "/mcp"
	openCodeMCPRegistryPointer = "/servers"
	openCodeMCPConfigPath      = "opencode.json"
	openCodeMCPRegistryPath    = "opencode.json.mainframe-mcp.json"
)

func loadMCPProjections(
	manifests []bundleManifest,
	catalog mcpcatalog.Catalog,
) ([]MCPProjection, error) {
	var result []MCPProjection
	for _, manifest := range manifests {
		component := domain.ComponentID(manifest.Component)
		identifiers := make([]string, len(manifest.MCPProjections))
		for index, record := range manifest.MCPProjections {
			identifiers[index] = record.ID
		}
		if !sortedUnique(identifiers) {
			return nil, fmt.Errorf("MCP projections must be sorted with unique ids")
		}
		for _, record := range manifest.MCPProjections {
			projection, err := loadMCPProjection(component, record, catalog)
			if err != nil {
				return nil, fmt.Errorf("MCP projection %q: %w", record.ID, err)
			}
			result = append(result, projection)
		}
	}
	sort.Slice(result, func(left, right int) bool { return result[left].ID < result[right].ID })
	return result, nil
}

func ValidateMCPProjections(
	projections []MCPProjection,
	catalog mcpcatalog.Catalog,
) error {
	identifiers := make([]string, len(projections))
	claims := make(map[domain.Location]map[string]bool)
	for index, projection := range projections {
		identifiers[index] = projection.ID
		if err := validateLoadedMCPProjection(projection, catalog); err != nil {
			return fmt.Errorf("MCP projection %q: %w", projection.ID, err)
		}
		entries := claims[projection.Target]
		if entries == nil {
			entries = make(map[string]bool)
			claims[projection.Target] = entries
		}
		if entries[projection.EntryKey] {
			return fmt.Errorf("MCP projection %q has duplicate entry claim", projection.ID)
		}
		entries[projection.EntryKey] = true
	}
	if !sortedUnique(identifiers) {
		return fmt.Errorf("MCP projections must be sorted with unique ids")
	}
	return nil
}

func validateLoadedMCPProjection(
	projection MCPProjection,
	catalog mcpcatalog.Catalog,
) error {
	if !itemPattern.MatchString(projection.ID) ||
		projection.ComponentID != domain.ComponentOpenCode ||
		projection.Codec != MCPProjectionOpenCodeRemote ||
		projection.MapPointer != openCodeMCPMapPointer ||
		projection.RegistryEntriesPointer != openCodeMCPRegistryPointer ||
		projection.RegistrySchemaVersion != registrySchemaVersion ||
		projection.EntryKey != string(projection.ServerID) {
		return fmt.Errorf("invalid identity, codec, or pointer contract")
	}
	wantTarget := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: openCodeMCPConfigPath,
	}
	wantRegistry := domain.Location{
		Root: domain.RootOpenCodeConfig,
		Path: openCodeMCPRegistryPath,
	}
	if projection.Target != wantTarget || projection.RegistryTarget != wantRegistry {
		return fmt.Errorf("invalid adapter-local target")
	}
	record := mcpProjectionRecord{
		Server:  string(projection.ServerID),
		Profile: string(projection.ProfileID),
	}
	_, profile, err := loadMCPProjectionProfile(
		projection.ComponentID, record, catalog,
	)
	if err != nil {
		return err
	}
	desired, err := json.Marshal(map[string]string{
		"type": "remote",
		"url":  profile.Endpoint,
	})
	if err != nil {
		return err
	}
	if projection.DesiredEntry != string(desired) {
		return fmt.Errorf("desired entry does not match catalog profile")
	}
	return nil
}

func loadMCPProjection(
	component domain.ComponentID,
	record mcpProjectionRecord,
	catalog mcpcatalog.Catalog,
) (MCPProjection, error) {
	if err := validateMCPProjectionRecord(component, record); err != nil {
		return MCPProjection{}, err
	}
	target, registry, err := loadMCPProjectionLocations(component, record)
	if err != nil {
		return MCPProjection{}, err
	}
	server, profile, err := loadMCPProjectionProfile(component, record, catalog)
	if err != nil {
		return MCPProjection{}, err
	}
	desired, err := json.Marshal(map[string]string{
		"type": "remote",
		"url":  profile.Endpoint,
	})
	if err != nil {
		return MCPProjection{}, err
	}
	return MCPProjection{
		ID: record.ID, ComponentID: component,
		Codec:    MCPProjectionOpenCodeRemote,
		ServerID: server.ID, ProfileID: profile.ID,
		Target: target, MapPointer: record.MapPointer, EntryKey: record.EntryKey,
		RegistryTarget:         registry,
		RegistrySchemaVersion:  record.Registry.SchemaVersion,
		RegistryEntriesPointer: record.Registry.EntriesPointer,
		DesiredEntry:           string(desired),
	}, nil
}

func validateMCPProjectionRecord(
	component domain.ComponentID,
	record mcpProjectionRecord,
) error {
	if !itemPattern.MatchString(record.ID) ||
		!componentPattern.MatchString(record.Server) ||
		!componentPattern.MatchString(record.Profile) ||
		!componentPattern.MatchString(record.EntryKey) {
		return fmt.Errorf("invalid identity")
	}
	if MCPProjectionCodec(record.Codec) != MCPProjectionOpenCodeRemote ||
		component != domain.ComponentOpenCode {
		return fmt.Errorf("unsupported codec or component")
	}
	if record.MapPointer != openCodeMCPMapPointer ||
		record.Registry.EntriesPointer != openCodeMCPRegistryPointer ||
		record.Registry.SchemaVersion != registrySchemaVersion {
		return fmt.Errorf("unsupported pointer or registry schema")
	}
	if _, err := jsondocument.ParsePointer(record.MapPointer); err != nil {
		return fmt.Errorf("invalid map pointer: %w", err)
	}
	if _, err := jsondocument.ParsePointer(record.Registry.EntriesPointer); err != nil {
		return fmt.Errorf("invalid registry pointer: %w", err)
	}
	if record.EntryKey != record.Server {
		return fmt.Errorf("entry key must match server id")
	}
	return nil
}

func loadMCPProjectionLocations(
	component domain.ComponentID,
	record mcpProjectionRecord,
) (domain.Location, domain.Location, error) {
	target, err := location(record.Target)
	if err != nil {
		return domain.Location{}, domain.Location{}, err
	}
	registry, err := location(record.Registry.Target)
	if err != nil {
		return domain.Location{}, domain.Location{}, err
	}
	if err := validateComponentTarget(component, target, "MCP projection"); err != nil {
		return domain.Location{}, domain.Location{}, err
	}
	if err := validateComponentTarget(component, registry, "MCP projection registry"); err != nil {
		return domain.Location{}, domain.Location{}, err
	}
	if target.Path != openCodeMCPConfigPath || registry.Path != openCodeMCPRegistryPath ||
		locationsOverlap(target, registry) {
		return domain.Location{}, domain.Location{}, fmt.Errorf("unsupported target or registry")
	}
	return target, registry, nil
}

func loadMCPProjectionProfile(
	component domain.ComponentID,
	record mcpProjectionRecord,
	catalog mcpcatalog.Catalog,
) (mcpcatalog.Server, mcpcatalog.Profile, error) {
	server, exists := catalog.Server(mcpcatalog.ServerID(record.Server))
	if !exists {
		return mcpcatalog.Server{}, mcpcatalog.Profile{}, fmt.Errorf(
			"unknown catalog server %q", record.Server,
		)
	}
	profile, exists := server.Profile(mcpcatalog.ProfileID(record.Profile))
	if !exists {
		return mcpcatalog.Server{}, mcpcatalog.Profile{}, fmt.Errorf(
			"unknown catalog profile %q", record.Profile,
		)
	}
	status, reason := profile.Support(component)
	if status != mcpcatalog.Supported {
		return mcpcatalog.Server{}, mcpcatalog.Profile{}, fmt.Errorf(
			"profile is unsupported: %s", reason,
		)
	}
	if profile.Transport != mcpcatalog.TransportStreamableHTTP ||
		profile.Authentication.Kind != mcpcatalog.AuthenticationNone ||
		profile.Authentication.Placement != mcpcatalog.PlacementNone ||
		profile.Endpoint == "" || profile.ServiceCredential != nil {
		return mcpcatalog.Server{}, mcpcatalog.Profile{}, fmt.Errorf(
			"profile is incompatible with codec",
		)
	}
	return server, profile, nil
}
