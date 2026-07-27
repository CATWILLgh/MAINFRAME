package executor

import (
	"encoding/json"
	"fmt"
)

var legacyJournalFields = map[string]bool{
	"release": true, "desired": true, "status": true, "plan": true,
	"roots": true, "directories": true, "steps": true,
}

func upgradeLegacyJournal(payload []byte) ([]byte, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal(payload, &root); err != nil {
		return nil, err
	}
	if root["schema_version"] != nil || root["configurations"] != nil {
		return payload, nil
	}
	if !exactLegacyJournalFields(root) {
		return payload, nil
	}
	root["schema_version"] = json.RawMessage("2")
	root["configurations"] = json.RawMessage("[]")
	return json.Marshal(root)
}

func upgradeV2Journal(payload []byte) ([]byte, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal(payload, &root); err != nil {
		return nil, err
	}
	if string(root["schema_version"]) != "2" {
		return payload, nil
	}
	if err := requireJournalShape(payload, 2); err != nil {
		return nil, err
	}
	journal, err := decodeJournalPayload(payload)
	if err != nil {
		return nil, err
	}
	if journalHasPersistedIdentity(journal) {
		return nil, legacyIdentityError(2)
	}
	if err := validateV2Journal(&journal); err != nil {
		return nil, err
	}
	journal.SchemaVersion = 3
	return json.Marshal(journal)
}

func upgradeV3Journal(payload []byte) ([]byte, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal(payload, &root); err != nil {
		return nil, err
	}
	if string(root["schema_version"]) != "3" {
		return payload, nil
	}
	if err := requireJournalShape(payload, 3); err != nil {
		return nil, err
	}
	journal, err := decodeJournalPayload(payload)
	if err != nil {
		return nil, err
	}
	if journalHasPersistedIdentity(journal) {
		return nil, legacyIdentityError(3)
	}
	journal.SchemaVersion = CurrentJournalSchemaVersion
	return json.Marshal(journal)
}

func journalHasPersistedIdentity(journal Journal) bool {
	return len(journal.Roots) != 0 ||
		len(journal.Configurations) != 0 ||
		len(journal.Directories) != 0 ||
		len(journal.Steps) != 0
}

func legacyIdentityError(schemaVersion int) error {
	return fmt.Errorf(
		"schema %d identity cannot be recovered safely; preserve transaction.json "+
			"and recover it with a schema-%d-compatible mainframe binary",
		schemaVersion,
		schemaVersion,
	)
}

func validateV2Journal(journal *Journal) error {
	for transition := range journal.Configurations {
		for mutation := range journal.Configurations[transition].Mutations {
			current := &journal.Configurations[transition].Mutations[mutation]
			if !current.After.Exists {
				return fmt.Errorf("v2 configuration after-image must exist")
			}
			current.Disposition = ConfigurationPresent
		}
	}
	return validateJournalVersion(*journal, 2)
}

func exactLegacyJournalFields(root map[string]json.RawMessage) bool {
	if len(root) != len(legacyJournalFields) {
		return false
	}
	for field := range root {
		if !legacyJournalFields[field] {
			return false
		}
	}
	return true
}

func requireConfigurationsShape(payload []byte, schemaVersion int) error {
	var transitions []json.RawMessage
	if err := json.Unmarshal(payload, &transitions); err != nil {
		return fmt.Errorf("configurations: %w", err)
	}
	for index, rawTransition := range transitions {
		transition, err := requiredObject(
			rawTransition,
			"resource_ids",
			"mutations",
		)
		if err != nil {
			return fmt.Errorf("configuration %d: %w", index, err)
		}
		if isNull(transition["resource_ids"]) || isNull(transition["mutations"]) {
			return fmt.Errorf("configuration %d collections must be arrays", index)
		}
		if err := requireConfigurationMutationsShape(
			index,
			transition["mutations"],
			schemaVersion,
		); err != nil {
			return err
		}
	}
	return nil
}

func requireConfigurationMutationsShape(
	transitionIndex int,
	payload []byte,
	schemaVersion int,
) error {
	var mutations []json.RawMessage
	if err := json.Unmarshal(payload, &mutations); err != nil {
		return fmt.Errorf(
			"configuration %d mutations: %w",
			transitionIndex,
			err,
		)
	}
	for index, rawMutation := range mutations {
		if err := requireConfigurationMutationShape(
			rawMutation,
			schemaVersion,
		); err != nil {
			return fmt.Errorf(
				"configuration %d mutation %d: %w",
				transitionIndex,
				index,
				err,
			)
		}
	}
	return nil
}

func requireConfigurationMutationShape(payload []byte, schemaVersion int) error {
	fields := []string{
		"target", "before", "after", "parent", "private",
		"staged_name", "staged_identity", "phase", "finalized",
	}
	if schemaVersion >= 3 {
		fields = append([]string{"disposition"}, fields...)
	}
	mutation, err := requiredObject(
		payload,
		fields...,
	)
	if err != nil {
		return err
	}
	for name, fields := range map[string][]string{
		"target":          {"root", "path"},
		"before":          {"exists", "sha256", "mode", "entry"},
		"after":           {"exists", "sha256", "mode", "entry"},
		"parent":          identityFields(schemaVersion),
		"private":         {"name", "identity"},
		"staged_identity": identityFields(schemaVersion),
	} {
		if _, err := requiredObject(mutation[name], fields...); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
	}
	for _, name := range []string{"before", "after"} {
		var image map[string]json.RawMessage
		if err := json.Unmarshal(mutation[name], &image); err != nil {
			return err
		}
		if _, err := requiredObject(
			image["entry"],
			identityFields(schemaVersion)...,
		); err != nil {
			return fmt.Errorf("%s entry: %w", name, err)
		}
	}
	var private map[string]json.RawMessage
	if err := json.Unmarshal(mutation["private"], &private); err != nil {
		return err
	}
	if _, err := requiredObject(
		private["identity"],
		identityFields(schemaVersion)...,
	); err != nil {
		return fmt.Errorf("private identity: %w", err)
	}
	return nil
}
