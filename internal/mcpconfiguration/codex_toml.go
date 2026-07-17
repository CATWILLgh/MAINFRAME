package mcpconfiguration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"

	"github.com/pelletier/go-toml/v2"
)

const (
	codexLayoutEmpty        = "empty"
	codexLayoutNewline      = "suffix-newline"
	codexLayoutUnterminated = "suffix-unterminated"
)

type codexBlockMatch struct {
	start   int
	layout  string
	newline string
}

func addCodexManagedBlock(raw []byte, entryKey, desiredRaw string) ([]byte, error) {
	if codexMarkerPresent(raw, entryKey) {
		return nil, fmt.Errorf("Codex MCP managed marker already exists")
	}
	endpoint, err := codexEntryURL(desiredRaw)
	if err != nil {
		return nil, err
	}
	layout, newline, separator := codexAppendLayout(raw)
	block, err := renderCodexManagedBlock(entryKey, endpoint, layout, newline)
	if err != nil {
		return nil, err
	}
	after := append(append(append([]byte(nil), raw...), separator...), block...)
	if err := validateCodexTOMLChange(raw, after, entryKey, desiredRaw, true); err != nil {
		return nil, err
	}
	return after, nil
}

func updateCodexManagedBlock(
	raw []byte,
	entryKey string,
	ownedRaw string,
	desiredRaw string,
) ([]byte, error) {
	match, err := findCodexManagedSuffix(raw, entryKey, ownedRaw)
	if err != nil {
		return nil, err
	}
	endpoint, err := codexEntryURL(desiredRaw)
	if err != nil {
		return nil, err
	}
	block, err := renderCodexManagedBlock(
		entryKey,
		endpoint,
		match.layout,
		match.newline,
	)
	if err != nil {
		return nil, err
	}
	replacement := append(codexBlockSeparator(match.layout, match.newline), block...)
	after := append(append([]byte(nil), raw[:match.start]...), replacement...)
	if err := validateCodexTOMLChange(raw, after, entryKey, desiredRaw, true); err != nil {
		return nil, err
	}
	return after, nil
}

func removeCodexManagedBlock(
	raw []byte,
	entryKey string,
	ownedRaw string,
) ([]byte, error) {
	match, err := findCodexManagedSuffix(raw, entryKey, ownedRaw)
	if err != nil {
		return nil, err
	}
	after := append([]byte(nil), raw[:match.start]...)
	if err := validateCodexTOMLChange(raw, after, entryKey, "", false); err != nil {
		return nil, err
	}
	return after, nil
}

func findCodexManagedSuffix(
	raw []byte,
	entryKey string,
	ownedRaw string,
) (codexBlockMatch, error) {
	endpoint, err := codexEntryURL(ownedRaw)
	if err != nil {
		return codexBlockMatch{}, err
	}
	var matches []codexBlockMatch
	for _, newline := range []string{"\n", "\r\n"} {
		for _, layout := range []string{
			codexLayoutEmpty,
			codexLayoutNewline,
			codexLayoutUnterminated,
		} {
			block, renderErr := renderCodexManagedBlock(
				entryKey,
				endpoint,
				layout,
				newline,
			)
			if renderErr != nil {
				return codexBlockMatch{}, renderErr
			}
			candidate := append(codexBlockSeparator(layout, newline), block...)
			if bytes.HasSuffix(raw, candidate) {
				matches = append(matches, codexBlockMatch{
					start: len(raw) - len(candidate), layout: layout, newline: newline,
				})
			}
		}
	}
	if len(matches) != 1 {
		return codexBlockMatch{}, fmt.Errorf("Codex MCP managed block is not one exact suffix")
	}
	return matches[0], nil
}

func renderCodexManagedBlock(
	entryKey string,
	endpoint string,
	layout string,
	newline string,
) ([]byte, error) {
	encodedEndpoint, err := json.Marshal(endpoint)
	if err != nil {
		return nil, fmt.Errorf("encode Codex MCP URL: %w", err)
	}
	encodedKey, err := json.Marshal(entryKey)
	if err != nil {
		return nil, fmt.Errorf("encode Codex MCP key: %w", err)
	}
	lines := []string{
		codexBeginMarker(entryKey, layout),
		"[mcp_servers." + string(encodedKey) + "]",
		"url = " + string(encodedEndpoint),
		codexEndMarker(entryKey),
		"",
	}
	block := []byte(strings.Join(lines, newline))
	var parsed map[string]any
	if err := toml.Unmarshal(block, &parsed); err != nil {
		return nil, fmt.Errorf("render Codex MCP block: %w", err)
	}
	entry, present := codexSemanticEntry(parsed, entryKey)
	if !present || !reflect.DeepEqual(entry, map[string]any{"url": endpoint}) {
		return nil, fmt.Errorf("rendered Codex MCP URL does not match the catalog")
	}
	return block, nil
}

func codexAppendLayout(raw []byte) (string, string, []byte) {
	if len(raw) == 0 {
		return codexLayoutEmpty, "\n", nil
	}
	newline := codexNewline(raw)
	if bytes.HasSuffix(raw, []byte(newline)) {
		return codexLayoutNewline, newline, []byte(newline)
	}
	return codexLayoutUnterminated, newline, []byte(newline + newline)
}

func codexNewline(raw []byte) string {
	index := bytes.LastIndexByte(raw, '\n')
	if index > 0 && raw[index-1] == '\r' {
		return "\r\n"
	}
	return "\n"
}

func codexBlockSeparator(layout, newline string) []byte {
	switch layout {
	case codexLayoutEmpty:
		return nil
	case codexLayoutNewline:
		return []byte(newline)
	case codexLayoutUnterminated:
		return []byte(newline + newline)
	default:
		return nil
	}
}

func codexMarkerPresent(raw []byte, entryKey string) bool {
	return bytes.Contains(raw, []byte("# MAINFRAME managed MCP v1 "+entryKey+" ")) ||
		bytes.Contains(raw, []byte(codexEndMarker(entryKey)))
}

func codexBeginMarker(entryKey, layout string) string {
	return "# MAINFRAME managed MCP v1 " + entryKey + " " + layout + " begin"
}

func codexEndMarker(entryKey string) string {
	return "# MAINFRAME managed MCP v1 " + entryKey + " end"
}

func validateCodexTOMLChange(
	before []byte,
	after []byte,
	entryKey string,
	desiredRaw string,
	desiredPresent bool,
) error {
	beforeRoot, err := parseCodexTOML(before)
	if err != nil {
		return fmt.Errorf("parse Codex MCP before-image: %w", err)
	}
	afterRoot, err := parseCodexTOML(after)
	if err != nil {
		return fmt.Errorf("parse Codex MCP after-image: %w", err)
	}
	entry, present := codexSemanticEntry(afterRoot, entryKey)
	if present != desiredPresent {
		return fmt.Errorf("Codex MCP after-image has an unexpected managed entry")
	}
	if desiredPresent {
		endpoint, endpointErr := codexEntryURL(desiredRaw)
		if endpointErr != nil {
			return endpointErr
		}
		if !reflect.DeepEqual(entry, map[string]any{"url": endpoint}) {
			return fmt.Errorf("Codex MCP after-image entry does not match the catalog")
		}
	}
	stripCodexSemanticEntry(beforeRoot, entryKey)
	stripCodexSemanticEntry(afterRoot, entryKey)
	if !reflect.DeepEqual(beforeRoot, afterRoot) {
		return fmt.Errorf("Codex MCP after-image changed unrelated TOML semantics")
	}
	return nil
}

func parseCodexTOML(raw []byte) (map[string]any, error) {
	result := make(map[string]any)
	if strings.TrimSpace(string(raw)) == "" {
		return result, nil
	}
	if err := toml.Unmarshal(raw, &result); err != nil {
		return nil, err
	}
	return result, nil
}

func codexSemanticEntry(root map[string]any, entryKey string) (any, bool) {
	servers, valid := root["mcp_servers"].(map[string]any)
	if !valid {
		return nil, false
	}
	entry, present := servers[entryKey]
	return entry, present
}

func stripCodexSemanticEntry(root map[string]any, entryKey string) {
	servers, valid := root["mcp_servers"].(map[string]any)
	if !valid {
		return
	}
	delete(servers, entryKey)
	if len(servers) == 0 {
		delete(root, "mcp_servers")
	}
}
