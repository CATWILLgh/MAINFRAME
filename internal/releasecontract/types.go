package releasecontract

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

const (
	bundleSchemaVersion  = 2
	releaseSchemaVersion = 2
	mcpCatalogPath       = "metadata/mcp-catalog.json"
)

const (
	bundleKind  = "mainframe-bundle"
	releaseKind = "mainframe-release"
)

type ResourceStrategy string

const (
	StrategyJSONKeyMerge       ResourceStrategy = "json-key-merge"
	StrategySeedIfAbsent       ResourceStrategy = "seed-if-absent"
	StrategyEnsureDir          ResourceStrategy = "ensure-directory"
	StrategyShellLine          ResourceStrategy = "shell-line"
	StrategyShellLineIfPresent ResourceStrategy = "shell-line-if-present"
	StrategyManualAction       ResourceStrategy = "manual-action"
)

func (strategy ResourceStrategy) valid() bool {
	switch strategy {
	case StrategyJSONKeyMerge,
		StrategySeedIfAbsent,
		StrategyEnsureDir,
		StrategyShellLine,
		StrategyShellLineIfPresent,
		StrategyManualAction:
		return true
	default:
		return false
	}
}

type SupportStatus string

const (
	SupportUnimplemented SupportStatus = "unimplemented"
	SupportSupported     SupportStatus = "supported"
)

type ExternalStateKind string

const (
	ExternalStateCodexHookTrust ExternalStateKind = "codex-hook-trust-v1"
)

type Resource struct {
	ID                   string
	ComponentID          domain.ComponentID
	Strategy             ResourceStrategy
	SourcePath           domain.ArtifactPath
	Target               domain.Location
	LegacySourceSuffixes []domain.ArtifactPath
	Observation          SupportStatus
	Apply                SupportStatus
	DesiredLine          string
	OwnedJSONFields      []JSONField
	JSONMapOwnership     *JSONMapOwnership
	ExternalState        *ExternalStateDescriptor
}

type JSONField struct {
	Pointer string
	Desired string
}

type JSONMapOwnership struct {
	MapPointer            string
	EntrySchema           string
	DesiredMap            string
	RegistryTarget        domain.Location
	RegistrySchemaVersion int
	EntriesPointer        string
}

type ExternalStateDescriptor struct {
	Kind ExternalStateKind
}

type Release struct {
	ID             string
	IndexSHA256    string
	Model          installmodel.Model
	Resources      []Resource
	MCPCatalog     mcpcatalog.Catalog
	MCPProjections []MCPProjection
}

type MCPProjectionCodec string

const (
	MCPProjectionAntigravityGlobalHTTP MCPProjectionCodec = "antigravity-global-http-v1"
	MCPProjectionClaudeUserHTTP        MCPProjectionCodec = "claude-user-http-v1"
	MCPProjectionCodexUserHTTP         MCPProjectionCodec = "codex-user-http-v1"
	MCPProjectionOpenCodeRemote        MCPProjectionCodec = "opencode-remote-v1"
)

type MCPProjectionDocumentFormat string

const (
	MCPProjectionDocumentJSON MCPProjectionDocumentFormat = "json"
	MCPProjectionDocumentTOML MCPProjectionDocumentFormat = "toml"
)

type MCPProjection struct {
	ID                     string
	ComponentID            domain.ComponentID
	Codec                  MCPProjectionCodec
	ServerID               mcpcatalog.ServerID
	ProfileID              mcpcatalog.ProfileID
	Target                 domain.Location
	MapPointer             string
	EntryKey               string
	RegistryTarget         domain.Location
	RegistrySchemaVersion  int
	RegistryEntriesPointer string
	DesiredEntry           string
}

func (projection MCPProjection) TargetDocumentFormat() MCPProjectionDocumentFormat {
	contract, exists := mcpProjectionContract(projection.ComponentID, projection.Codec)
	if !exists {
		return ""
	}
	return contract.documentFormat
}

type releaseIndex struct {
	SchemaVersion int             `json:"schema_version"`
	Kind          string          `json:"kind"`
	ReleaseID     string          `json:"release_id"`
	MCPCatalog    catalogEntry    `json:"mcp_catalog"`
	Manifests     []manifestEntry `json:"manifests"`
}

type catalogEntry struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type manifestEntry struct {
	Component string `json:"component"`
	Path      string `json:"path"`
	SHA256    string `json:"sha256"`
}

type bundleManifest struct {
	SchemaVersion   int                   `json:"schema_version"`
	Kind            string                `json:"kind"`
	Component       string                `json:"component"`
	Dependencies    []string              `json:"dependencies"`
	InstallUnits    []installUnit         `json:"install_units"`
	LegacyArtifacts []legacyArtifact      `json:"legacy_artifacts"`
	Resources       []resourceRecord      `json:"resources"`
	PayloadFiles    []payloadFile         `json:"payload_files"`
	RuntimeProfile  map[string]string     `json:"runtime_profile"`
	MCPProjections  []mcpProjectionRecord `json:"mcp_projections"`
}

type mcpProjectionRecord struct {
	ID         string                  `json:"id"`
	Codec      string                  `json:"codec"`
	Server     string                  `json:"server"`
	Profile    string                  `json:"profile"`
	Target     locationRecord          `json:"target"`
	MapPointer string                  `json:"map_pointer"`
	EntryKey   string                  `json:"entry_key"`
	Registry   ownershipRegistryRecord `json:"registry"`
}

type installUnit struct {
	ID                   string         `json:"id"`
	Kind                 string         `json:"kind"`
	Source               string         `json:"source"`
	Target               locationRecord `json:"target"`
	LegacySourceSuffixes []string       `json:"legacy_source_suffixes,omitempty"`
}

type legacyArtifact struct {
	Target         locationRecord `json:"target"`
	TargetSuffixes []string       `json:"target_suffixes"`
}

type resourceRecord struct {
	ID                   string                   `json:"id"`
	Strategy             string                   `json:"strategy"`
	Source               string                   `json:"source,omitempty"`
	Target               locationRecord           `json:"target"`
	LegacySourceSuffixes []string                 `json:"legacy_source_suffixes,omitempty"`
	Observation          string                   `json:"observation"`
	Apply                string                   `json:"apply"`
	OwnedJSONPointers    optionalStringList       `json:"owned_json_pointers,omitempty"`
	Ownership            optionalJSONMapOwnership `json:"ownership,omitempty"`
	ExternalState        optionalExternalState    `json:"external_state,omitempty"`
}

type optionalStringList struct {
	Present bool
	Values  []string
}

type optionalJSONMapOwnership struct {
	Present bool
	Value   jsonMapOwnershipRecord
}

type jsonMapOwnershipRecord struct {
	Kind        string                  `json:"kind"`
	MapPointer  string                  `json:"map_pointer"`
	EntrySchema string                  `json:"entry_schema"`
	Registry    ownershipRegistryRecord `json:"registry"`
}

type ownershipRegistryRecord struct {
	Target         locationRecord `json:"target"`
	SchemaVersion  int            `json:"schema_version"`
	EntriesPointer string         `json:"entries_pointer"`
}

type externalStateRecord struct {
	Kind string `json:"kind"`
}

type optionalExternalState struct {
	Present bool
	Value   externalStateRecord
}

type locationRecord struct {
	Root string `json:"root"`
	Path string `json:"path"`
}

type payloadFile struct {
	Path   string `json:"path"`
	Mode   string `json:"mode"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256"`
}
