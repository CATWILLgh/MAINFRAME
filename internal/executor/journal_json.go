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
	journal.SchemaVersion = CurrentJournalSchemaVersion
	if journal.Desired == nil {
		journal.Desired = []domain.ComponentID{}
	}
	if journal.Plan.Operations == nil {
		journal.Plan.Operations = []domain.Operation{}
	}
	if journal.Roots == nil {
		journal.Roots = []RootSnapshot{}
	}
	if journal.Configurations == nil {
		journal.Configurations = []JournalConfigurationTransition{}
	}
	if journal.Directories == nil {
		journal.Directories = []JournalDirectory{}
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
	var err error
	payload, err = upgradeLegacyJournal(payload)
	if err != nil {
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
	if err := validateJournalSchema(journal); err != nil {
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
	root, err := requiredObject(
		payload,
		"schema_version", "release", "desired", "status", "plan", "roots",
		"configurations", "directories", "steps",
	)
	if err != nil {
		return err
	}
	if _, err := requiredObject(root["release"], "id", "index_sha256"); err != nil {
		return fmt.Errorf("release: %w", err)
	}
	plan, err := requiredObject(root["plan"], "operations")
	if err != nil {
		return fmt.Errorf("plan: %w", err)
	}
	if isNull(root["desired"]) || isNull(plan["operations"]) ||
		isNull(root["roots"]) || isNull(root["configurations"]) ||
		isNull(root["directories"]) || isNull(root["steps"]) {
		return fmt.Errorf("journal collections must be arrays")
	}
	if err := requireOperationsShape(plan["operations"]); err != nil {
		return err
	}
	if err := requireRootsShape(root["roots"]); err != nil {
		return err
	}
	if err := requireConfigurationsShape(root["configurations"]); err != nil {
		return err
	}
	if err := requireDirectoriesShape(root["directories"]); err != nil {
		return err
	}
	return requireStepsShape(root["steps"])
}

func requireStepsShape(payload []byte) error {
	var steps []json.RawMessage
	if err := json.Unmarshal(payload, &steps); err != nil {
		return fmt.Errorf("steps: %w", err)
	}
	for index, rawStep := range steps {
		step, err := requiredObject(
			rawStep,
			"kind", "location", "source_path", "before", "after", "parent",
			"private", "staged_name", "staged_identity", "retained_name",
			"phase", "finalized",
		)
		if err != nil {
			return fmt.Errorf("step %d: %w", index, err)
		}
		for name, fields := range map[string][]string{
			"location":        {"root", "path"},
			"before":          {"exists", "raw_target", "entry"},
			"after":           {"exists", "raw_target", "entry"},
			"parent":          {"device", "inode"},
			"private":         {"name", "identity"},
			"staged_identity": {"device", "inode"},
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
		var private map[string]json.RawMessage
		if err := json.Unmarshal(step["private"], &private); err != nil {
			return fmt.Errorf("step %d private: %w", index, err)
		}
		if _, err := requiredObject(private["identity"], "device", "inode"); err != nil {
			return fmt.Errorf("step %d private identity: %w", index, err)
		}
	}
	return nil
}

func requireOperationsShape(payload []byte) error {
	var operations []json.RawMessage
	if err := json.Unmarshal(payload, &operations); err != nil {
		return fmt.Errorf("plan operations: %w", err)
	}
	for index, rawOperation := range operations {
		operation, err := requiredObject(
			rawOperation,
			"component_id", "kind", "artifact", "source_path",
		)
		if err != nil {
			return fmt.Errorf("plan operation %d: %w", index, err)
		}
		artifact, err := requiredObject(operation["artifact"], "location")
		if err != nil {
			return fmt.Errorf("plan operation %d artifact: %w", index, err)
		}
		if _, err := requiredObject(artifact["location"], "root", "path"); err != nil {
			return fmt.Errorf("plan operation %d location: %w", index, err)
		}
	}
	return nil
}

func requireRootsShape(payload []byte) error {
	var roots []json.RawMessage
	if err := json.Unmarshal(payload, &roots); err != nil {
		return fmt.Errorf("roots: %w", err)
	}
	for index, rawRoot := range roots {
		root, err := requiredObject(
			rawRoot,
			"root", "anchor_path", "anchor_identity", "root_path",
		)
		if err != nil {
			return fmt.Errorf("root %d: %w", index, err)
		}
		if _, err := requiredObject(root["anchor_identity"], "device", "inode"); err != nil {
			return fmt.Errorf("root %d anchor identity: %w", index, err)
		}
	}
	return nil
}

func requireDirectoriesShape(payload []byte) error {
	var directories []json.RawMessage
	if err := json.Unmarshal(payload, &directories); err != nil {
		return fmt.Errorf("directories: %w", err)
	}
	for index, rawDirectory := range directories {
		directory, err := requiredObject(
			rawDirectory,
			"target", "mode", "parent", "private_name", "entry", "phase", "finalized",
		)
		if err != nil {
			return fmt.Errorf("directory %d: %w", index, err)
		}
		for name, fields := range map[string][]string{
			"target": {"root", "path"},
			"parent": {"device", "inode"},
			"entry":  {"device", "inode"},
		} {
			if _, err := requiredObject(directory[name], fields...); err != nil {
				return fmt.Errorf("directory %d %s: %w", index, name, err)
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
