package configuration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
)

func encodeMergedDecision(
	value any,
	nestedOrder map[string]string,
	orderSources ...string,
) (string, error) {
	entries, isMap := value.(map[string]any)
	if !isMap {
		raw, err := json.Marshal(value)
		return string(raw), err
	}
	return encodeOrderedDecisionMap(entries, nestedOrder, orderSources...)
}

func encodeOrderedDecisionMap(
	values map[string]any,
	nestedOrder map[string]string,
	orderSources ...string,
) (string, error) {
	keys, err := orderedDecisionKeys(values, orderSources...)
	if err != nil {
		return "", err
	}
	var output bytes.Buffer
	output.WriteByte('{')
	for index, key := range keys {
		if index > 0 {
			output.WriteByte(',')
		}
		keyJSON, err := json.Marshal(key)
		if err != nil {
			return "", err
		}
		valueJSON, err := encodeDecisionRule(values[key], nestedOrder[key])
		if err != nil {
			return "", err
		}
		output.Write(keyJSON)
		output.WriteByte(':')
		output.Write(valueJSON)
	}
	output.WriteByte('}')
	return output.String(), nil
}

func orderedDecisionKeys(
	values map[string]any,
	orderSources ...string,
) ([]string, error) {
	result := make([]string, 0, len(values))
	seen := make(map[string]bool, len(values))
	for _, raw := range orderSources {
		keys, err := topLevelObjectKeys(raw)
		if err != nil {
			return nil, err
		}
		for _, key := range keys {
			if _, exists := values[key]; exists && !seen[key] {
				result = append(result, key)
				seen[key] = true
			}
		}
	}
	var remaining []string
	for key := range values {
		if !seen[key] {
			remaining = append(remaining, key)
		}
	}
	sort.Strings(remaining)
	return append(result, remaining...), nil
}

func topLevelObjectKeys(raw string) ([]string, error) {
	decoder := json.NewDecoder(bytes.NewReader([]byte(raw)))
	start, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	if delimiter, valid := start.(json.Delim); !valid || delimiter != '{' {
		return nil, nil
	}
	var keys []string
	for decoder.More() {
		key, err := decoder.Token()
		if err != nil {
			return nil, err
		}
		name, valid := key.(string)
		if !valid {
			return nil, fmt.Errorf("decision map key is not a string")
		}
		var ignored json.RawMessage
		if err := decoder.Decode(&ignored); err != nil {
			return nil, err
		}
		keys = append(keys, name)
	}
	_, err = decoder.Token()
	return keys, err
}

func encodeDecisionRule(value any, nestedOrder string) ([]byte, error) {
	if _, nested := value.(map[string]any); nested && nestedOrder != "" {
		return []byte(nestedOrder), nil
	}
	return json.Marshal(value)
}
