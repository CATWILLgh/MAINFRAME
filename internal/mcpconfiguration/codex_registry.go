package mcpconfiguration

import (
	"encoding/json"
	"fmt"
)

const codexManagedRegistryFormat = "codex-toml-block-v1"

type codexRegistryEntry struct {
	Format string          `json:"format"`
	Entry  json.RawMessage `json:"entry"`
}

func decodeCodexRegistryEntry(raw []byte) (string, bool, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return "", false, fmt.Errorf("MCP ownership registry entry is invalid")
	}
	_, hasFormat := object["format"]
	_, hasEntry := object["entry"]
	if !hasFormat && !hasEntry {
		return "", false, nil
	}
	if len(object) != 2 || !hasFormat || !hasEntry {
		return "", false, fmt.Errorf("Codex MCP ownership provenance is invalid")
	}
	var wrapper codexRegistryEntry
	if err := json.Unmarshal(raw, &wrapper); err != nil ||
		wrapper.Format != codexManagedRegistryFormat {
		return "", false, fmt.Errorf("Codex MCP ownership provenance is invalid")
	}
	entry, err := validateCodexSemanticEntry(wrapper.Entry)
	if err != nil {
		return "", false, err
	}
	return entry, true, nil
}

func encodeCodexRegistryEntry(raw string) (string, error) {
	entry, err := validateCodexSemanticEntry([]byte(raw))
	if err != nil {
		return "", err
	}
	wrapper := codexRegistryEntry{
		Format: codexManagedRegistryFormat,
		Entry:  json.RawMessage(entry),
	}
	encoded, err := json.Marshal(wrapper)
	if err != nil {
		return "", fmt.Errorf("encode Codex MCP ownership provenance: %w", err)
	}
	return string(encoded), nil
}

func validateCodexSemanticEntry(raw []byte) (string, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || len(object) != 1 {
		return "", fmt.Errorf("Codex MCP entry must contain exactly one URL")
	}
	var endpoint string
	if err := json.Unmarshal(object["url"], &endpoint); err != nil || endpoint == "" {
		return "", fmt.Errorf("Codex MCP entry URL is invalid")
	}
	canonical, err := json.Marshal(map[string]string{"url": endpoint})
	if err != nil {
		return "", fmt.Errorf("encode Codex MCP entry: %w", err)
	}
	return string(canonical), nil
}

func codexEntryURL(raw string) (string, error) {
	canonical, err := validateCodexSemanticEntry([]byte(raw))
	if err != nil {
		return "", err
	}
	var entry map[string]string
	if err := json.Unmarshal([]byte(canonical), &entry); err != nil {
		return "", err
	}
	return entry["url"], nil
}
