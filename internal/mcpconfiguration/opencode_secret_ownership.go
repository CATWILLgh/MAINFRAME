package mcpconfiguration

import (
	"encoding/json"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const openCodeSecretRegistryFormat = "opencode-file-secret-v1"
const openCodeSecretBackend = "environment"

type openCodeSecretRegistryEntry struct {
	Format           string          `json:"format"`
	Profile          string          `json:"profile"`
	SecretBackend    string          `json:"secret_backend"`
	SecretReference  string          `json:"secret_reference"`
	Entry            json.RawMessage `json:"entry"`
	SecretFileSHA256 string          `json:"secret_file_sha256"`
}

func encodeOpenCodeSecretRegistryEntry(
	projection releasecontract.MCPProjection,
	binding CredentialBinding,
) (string, error) {
	entry := openCodeSecretRegistryEntry{
		Format:           openCodeSecretRegistryFormat,
		Profile:          string(projection.ProfileID),
		SecretBackend:    openCodeSecretBackend,
		SecretReference:  binding.EnvironmentVariable,
		Entry:            json.RawMessage(projection.DesiredEntry),
		SecretFileSHA256: configuration.DeferredSecretDigestPlaceholder,
	}
	if err := validateOpenCodeSecretRegistryEntry(entry, true); err != nil {
		return "", err
	}
	payload, err := json.Marshal(entry)
	if err != nil {
		return "", fmt.Errorf("encode OpenCode MCP ownership metadata: %w", err)
	}
	return string(payload), nil
}

func decodeOpenCodeSecretRegistryEntry(
	raw string,
	secretFile mcpFileSnapshot,
) (string, bool, bool, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &object); err != nil {
		return "", false, false, nil
	}
	format, exists := object["format"]
	if !exists || string(format) != `"`+openCodeSecretRegistryFormat+`"` {
		return "", false, false, nil
	}
	if len(object) != 6 {
		return "", false, true, fmt.Errorf(
			"OpenCode MCP ownership metadata is invalid",
		)
	}
	var entry openCodeSecretRegistryEntry
	if err := json.Unmarshal([]byte(raw), &entry); err != nil ||
		validateOpenCodeSecretRegistryEntry(entry, false) != nil {
		return "", false, true, fmt.Errorf(
			"OpenCode MCP ownership metadata is invalid",
		)
	}
	materializable := secretFile.problem == "" &&
		secretFile.present &&
		secretFile.mode == 0o600 &&
		secretFile.sha256 == entry.SecretFileSHA256
	return string(entry.Entry), materializable, true, nil
}

func validateOpenCodeSecretRegistryEntry(
	entry openCodeSecretRegistryEntry,
	allowPlaceholder bool,
) error {
	digestValid := antigravitySecretDigestPattern.MatchString(
		entry.SecretFileSHA256,
	)
	if allowPlaceholder {
		digestValid = entry.SecretFileSHA256 ==
			configuration.DeferredSecretDigestPlaceholder
	}
	var desired map[string]any
	if err := json.Unmarshal(entry.Entry, &desired); err != nil || desired == nil {
		return fmt.Errorf("invalid OpenCode MCP ownership metadata")
	}
	if entry.Format != openCodeSecretRegistryFormat ||
		entry.Profile != "remote-api-key" ||
		entry.SecretBackend != openCodeSecretBackend ||
		!antigravitySecretReferencePattern.MatchString(entry.SecretReference) ||
		!digestValid {
		return fmt.Errorf("invalid OpenCode MCP ownership metadata")
	}
	return nil
}
