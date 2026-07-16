package configuration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"
)

func orderedRuleMap(raw string) (map[string]string, error) {
	if len(raw) == 0 || raw[0] != '{' {
		return map[string]string{}, nil
	}
	var entries map[string]json.RawMessage
	if err := json.Unmarshal([]byte(raw), &entries); err != nil {
		return nil, err
	}
	result := make(map[string]string)
	for action, rule := range entries {
		if len(rule) == 0 || rule[0] != '{' {
			continue
		}
		normalized, err := normalizeOrderedRule(rule)
		if err != nil {
			return nil, err
		}
		result[action] = normalized
	}
	return result, nil
}

func normalizeOrderedRule(raw json.RawMessage) (string, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	start, err := decoder.Token()
	if err != nil {
		return "", err
	}
	if delimiter, valid := start.(json.Delim); !valid || delimiter != '{' {
		return "", fmt.Errorf("expected an object")
	}
	var result strings.Builder
	result.WriteByte('{')
	for first := true; decoder.More(); first = false {
		key, err := decoder.Token()
		if err != nil {
			return "", err
		}
		var value any
		if err := decoder.Decode(&value); err != nil {
			return "", err
		}
		keyJSON, err := json.Marshal(key)
		if err != nil {
			return "", err
		}
		valueJSON, err := json.Marshal(value)
		if err != nil {
			return "", err
		}
		if !first {
			result.WriteByte(',')
		}
		result.Write(keyJSON)
		result.WriteByte(':')
		result.Write(valueJSON)
	}
	if _, err := decoder.Token(); err != nil {
		return "", err
	}
	result.WriteByte('}')
	return result.String(), nil
}
