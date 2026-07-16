package executor

import (
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

func TestJournalJSONUpgradesExactLegacyLinkOnlyShape(t *testing.T) {
	legacy := fmt.Sprintf(
		`{"release":{"id":"release","index_sha256":"%s"},`+
			`"desired":[],"status":"in_progress","plan":{"operations":[]},`+
			`"roots":[],"directories":[],"steps":[]}`,
		testDigest("legacy"),
	)
	journal, err := decodeJournal([]byte(legacy))
	if err != nil {
		t.Fatalf("decodeJournal() error = %v", err)
	}
	if journal.SchemaVersion != CurrentJournalSchemaVersion ||
		journal.Configurations == nil ||
		len(journal.Configurations) != 0 {
		t.Fatalf("legacy upgrade = %#v", journal)
	}
}

func TestCurrentInMemoryLinkOnlyJournalEncodesCurrentShape(t *testing.T) {
	journal := journalWith(
		TransactionInProgress,
		installJournalStep("one", StepPrepared),
	)
	if err := validateJournal(*journal); err != nil {
		t.Fatalf("validate current fixture: %v", err)
	}
	payload, err := encodeJournal(*journal)
	if err != nil {
		t.Fatalf("encode current fixture: %v", err)
	}
	if !strings.Contains(string(payload), `"schema_version":2`) ||
		!strings.Contains(string(payload), `"configurations":[]`) {
		t.Fatalf("current fixture encoded incorrectly: %s", payload)
	}
}

func TestJournalJSONRejectsInexactLegacyShapes(t *testing.T) {
	digest := testDigest("legacy")
	tests := map[string]string{
		"unknown": fmt.Sprintf(
			`{"release":{"id":"release","index_sha256":"%s"},`+
				`"desired":[],"status":"in_progress","plan":{"operations":[]},`+
				`"roots":[],"directories":[],"steps":[],"extra":true}`,
			digest,
		),
		"missing": fmt.Sprintf(
			`{"release":{"id":"release","index_sha256":"%s"},`+
				`"desired":[],"status":"in_progress","plan":{"operations":[]},`+
				`"roots":[],"directories":[]}`,
			digest,
		),
		"duplicate": fmt.Sprintf(
			`{"release":{"id":"release","index_sha256":"%s"},`+
				`"desired":[],"status":"in_progress","status":"committed",`+
				`"plan":{"operations":[]},"roots":[],"directories":[],"steps":[]}`,
			digest,
		),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeJournal([]byte(payload)); err == nil {
				t.Fatal("decodeJournal() accepted an inexact legacy journal")
			}
		})
	}
}

func TestJournalJSONRejectsExplicitLegacySchemaVersion(t *testing.T) {
	payload, err := encodeJournal(*journalWith(
		TransactionInProgress,
		installJournalStep("one", StepPrepared),
	))
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	explicitVersionZero := strings.Replace(
		string(payload),
		`"schema_version":2`,
		`"schema_version":0`,
		1,
	)

	if _, err := decodeJournal([]byte(explicitVersionZero)); err == nil {
		t.Fatal("decodeJournal() accepted explicit schema version 0")
	}
}

func TestJournalJSONEncodesCurrentShapeWithoutPreparedBytes(t *testing.T) {
	const secret = "secret-sentinel-must-not-enter-journal"
	journal := configurationJournalFixture(StepPrepared, TransactionInProgress)
	journal.Configurations[0].Mutations[0].After.SHA256 = digestString(secret)

	payload, err := encodeJournal(journal)
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	if strings.Contains(string(payload), secret) {
		t.Fatal("journal contains prepared configuration bytes")
	}
	var root map[string]json.RawMessage
	if err := json.Unmarshal(payload, &root); err != nil {
		t.Fatalf("decode encoded journal: %v", err)
	}
	wantFields := []string{
		"configurations", "desired", "directories", "plan", "release",
		"roots", "schema_version", "status", "steps",
	}
	gotFields := make([]string, 0, len(root))
	for field := range root {
		gotFields = append(gotFields, field)
	}
	sortStrings(gotFields)
	if !reflect.DeepEqual(gotFields, wantFields) ||
		string(root["schema_version"]) != "2" ||
		string(root["configurations"]) == "null" {
		t.Fatalf("current journal shape = %s", payload)
	}
}

func TestJournalJSONRejectsInexactCurrentConfigurationShapes(t *testing.T) {
	valid, err := encodeJournal(
		configurationJournalFixture(StepPrepared, TransactionInProgress),
	)
	if err != nil {
		t.Fatalf("encode fixture: %v", err)
	}
	tests := map[string]func(map[string]any){
		"unknown root": func(root map[string]any) {
			root["unknown"] = true
		},
		"missing configurations": func(root map[string]any) {
			delete(root, "configurations")
		},
		"null configurations": func(root map[string]any) {
			root["configurations"] = nil
		},
		"unknown mutation": func(root map[string]any) {
			firstConfigurationMutation(root)["payload"] = "secret"
		},
		"missing mutation field": func(root map[string]any) {
			delete(firstConfigurationMutation(root), "after")
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			payload := mutateJournalJSON(t, valid, mutate)
			if _, err := decodeJournal(payload); err == nil {
				t.Fatal("decodeJournal() accepted an inexact current journal")
			}
		})
	}
}
