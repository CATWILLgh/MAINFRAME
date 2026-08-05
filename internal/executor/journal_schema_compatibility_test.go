package executor

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestJournalWritesV5AndRecoversLegacyV4SymlinkTransaction(t *testing.T) {
	journal := journalWith(
		TransactionInProgress,
		installJournalStep("one", StepPrepared),
	)
	payload, err := encodeJournal(*journal)
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	if !strings.Contains(string(payload), `"schema_version":5`) {
		t.Fatalf("current journal = %s", payload)
	}
	legacy := mutateJournalJSON(t, payload, func(root map[string]any) {
		root["schema_version"] = float64(4)
		removeWritableJournalFields(root)
	})
	decoded, err := decodeJournal(legacy)
	if err != nil {
		t.Fatalf("decodeJournal(v4) error = %v", err)
	}
	if decoded.SchemaVersion != 5 {
		t.Fatalf("decoded schema = %d", decoded.SchemaVersion)
	}
	fixture := newFixture(Preview{})
	fixture.store.journal = &decoded
	if _, err := fixture.executor().Recover(); err != nil {
		t.Fatalf("Recover(v4) error = %v", err)
	}
}

func TestJournalRejectsWritableFieldsAdvertisedAsV4(t *testing.T) {
	payload, err := encodeJournal(*journalWith(
		TransactionInProgress,
		installJournalStep("one", StepPrepared),
	))
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	legacy := mutateJournalJSON(t, payload, func(root map[string]any) {
		root["schema_version"] = float64(4)
		removeWritableJournalFields(root)
		firstStep(root)["materialization"] = string(domain.MaterializationWritableFile)
	})
	if _, err := decodeJournal(legacy); err == nil {
		t.Fatal("decodeJournal() accepted writable field under v4")
	}
}

func TestJournalRejectsUnknownFutureSchema(t *testing.T) {
	payload, err := encodeJournal(*journalWith(TransactionCommitted))
	if err != nil {
		t.Fatalf("encodeJournal() error = %v", err)
	}
	future := strings.Replace(string(payload), `"schema_version":5`, `"schema_version":6`, 1)
	if _, err := decodeJournal([]byte(future)); err == nil {
		t.Fatal("decodeJournal() accepted future schema")
	}
}

func removeWritableJournalFields(value any) {
	switch current := value.(type) {
	case map[string]any:
		for _, field := range []string{
			"source_sha256", "materialization", "file_before", "file_after",
			"content_sha256", "mode",
		} {
			delete(current, field)
		}
		for _, child := range current {
			removeWritableJournalFields(child)
		}
	case []any:
		for _, child := range current {
			removeWritableJournalFields(child)
		}
	}
}

func firstStep(root map[string]any) map[string]any {
	return root["steps"].([]any)[0].(map[string]any)
}
