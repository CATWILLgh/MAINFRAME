package executor

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"strings"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func encodeJournal(journal Journal) ([]byte, error) {
	if journal.Desired == nil {
		journal.Desired = []domain.ComponentID{}
	}
	if journal.Steps == nil {
		journal.Steps = []JournalMutation{}
	}
	return json.Marshal(journal)
}

func decodeJournal(payload []byte) (Journal, error) {
	if err := rejectDuplicateJSON(payload); err != nil {
		return Journal{}, err
	}
	if err := requireJournalShape(payload); err != nil {
		return Journal{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var journal Journal
	if err := decoder.Decode(&journal); err != nil {
		return Journal{}, err
	}
	if err := expectJSONEnd(decoder); err != nil {
		return Journal{}, err
	}
	return journal, nil
}

func rejectDuplicateJSON(payload []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.UseNumber()
	if err := scanJSONValue(decoder); err != nil {
		return err
	}
	return expectJSONEnd(decoder)
}

func scanJSONValue(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, isDelimiter := token.(json.Delim)
	if !isDelimiter {
		return nil
	}
	if delimiter == '[' {
		for decoder.More() {
			if err := scanJSONValue(decoder); err != nil {
				return err
			}
		}
		_, err = decoder.Token()
		return err
	}
	if delimiter != '{' {
		return fmt.Errorf("unexpected JSON delimiter %q", delimiter)
	}
	seen := make(map[string]bool)
	for decoder.More() {
		keyToken, err := decoder.Token()
		if err != nil {
			return err
		}
		key, ok := keyToken.(string)
		if !ok {
			return fmt.Errorf("JSON object key is not a string")
		}
		canonical := strings.ToLower(key)
		if seen[canonical] {
			return fmt.Errorf("duplicate JSON field %q", key)
		}
		seen[canonical] = true
		if err := scanJSONValue(decoder); err != nil {
			return err
		}
	}
	_, err = decoder.Token()
	return err
}

func expectJSONEnd(decoder *json.Decoder) error {
	if _, err := decoder.Token(); err != io.EOF {
		if err == nil {
			return fmt.Errorf("trailing JSON value")
		}
		return err
	}
	return nil
}

func requireJournalShape(payload []byte) error {
	root, err := requiredObject(payload, "release", "desired", "status", "steps")
	if err != nil {
		return err
	}
	if _, err := requiredObject(root["release"], "id", "index_sha256"); err != nil {
		return fmt.Errorf("release: %w", err)
	}
	var steps []json.RawMessage
	if isNull(root["desired"]) || isNull(root["steps"]) {
		return fmt.Errorf("desired and steps must be arrays")
	}
	if err := json.Unmarshal(root["steps"], &steps); err != nil {
		return fmt.Errorf("steps: %w", err)
	}
	for index, rawStep := range steps {
		step, err := requiredObject(
			rawStep,
			"kind", "location", "source_path", "before", "after", "parent", "state",
		)
		if err != nil {
			return fmt.Errorf("step %d: %w", index, err)
		}
		for name, fields := range map[string][]string{
			"location": {"root", "path"},
			"before":   {"exists", "raw_target", "entry"},
			"after":    {"exists", "raw_target", "entry"},
			"parent":   {"device", "inode"},
		} {
			if _, err := requiredObject(step[name], fields...); err != nil {
				return fmt.Errorf("step %d %s: %w", index, name, err)
			}
		}
		for _, name := range []string{"before", "after"} {
			var image map[string]json.RawMessage
			if err := json.Unmarshal(step[name], &image); err != nil {
				return fmt.Errorf("step %d %s: %w", index, name, err)
			}
			if _, err := requiredObject(image["entry"], "device", "inode"); err != nil {
				return fmt.Errorf("step %d %s entry: %w", index, name, err)
			}
		}
	}
	return nil
}

func requiredObject(payload []byte, fields ...string) (map[string]json.RawMessage, error) {
	if isNull(payload) {
		return nil, fmt.Errorf("object must not be null")
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(payload, &object); err != nil {
		return nil, err
	}
	for _, field := range fields {
		value, exists := object[field]
		if !exists || isNull(value) {
			return nil, fmt.Errorf("missing field %q", field)
		}
	}
	return object, nil
}

func isNull(payload []byte) bool {
	return bytes.Equal(bytes.TrimSpace(payload), []byte("null"))
}
