package executor

import (
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestValidateJournalAcceptsAllowedManagedDirectories(t *testing.T) {
	journal := directoryJournalFixture()

	if err := validateJournal(journal); err != nil {
		t.Fatalf("validateJournal() error = %v", err)
	}
}

func TestValidateJournalRejectsUnplannedOrMisorderedDirectories(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*Journal)
	}{
		{name: "unplanned", mutate: func(journal *Journal) {
			journal.Directories[1].Target.Path = ".codex/foreign"
		}},
		{name: "child before parent", mutate: func(journal *Journal) {
			journal.Directories[0], journal.Directories[1] =
				journal.Directories[1], journal.Directories[0]
		}},
		{name: "duplicate private name", mutate: func(journal *Journal) {
			journal.Directories[1].PrivateName = journal.Directories[0].PrivateName
		}},
		{name: "wrong root snapshot", mutate: func(journal *Journal) {
			journal.Roots[0].Root = domain.RootClaudeConfig
		}},
		{name: "invalid mode", mutate: func(journal *Journal) {
			journal.Directories[0].Mode = 0o777
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			journal := directoryJournalFixture()
			test.mutate(&journal)
			if err := validateJournal(journal); err == nil {
				t.Fatal("validateJournal() accepted an invalid directory journal")
			}
		})
	}
}

func TestCommittedJournalRequiresPublishedDirectories(t *testing.T) {
	journal := directoryJournalFixture()
	journal.Status = TransactionCommitted
	journal.Directories[1].Phase = StepStaged

	if err := validateJournal(journal); err == nil {
		t.Fatal("validateJournal() accepted an uncommitted directory")
	}
}

func directoryJournalFixture() Journal {
	operation := install("skills/mainframe", "bundles/codex/skills/mainframe")
	return Journal{
		SchemaVersion: CurrentJournalSchemaVersion,
		Release:       ReleaseIdentity{ID: "release", IndexSHA256: testDigest("directory")},
		Desired:       []domain.ComponentID{"codex"},
		Status:        TransactionInProgress,
		Plan:          domain.Plan{Operations: []domain.Operation{operation}},
		Roots: []RootSnapshot{{
			Root: domain.RootCodexConfig, AnchorPath: "/home/user",
			AnchorIdentity: testIdentity(1, 1),
			RootPath:       ".codex",
		}},
		Directories: []JournalDirectory{
			publishedDirectory(".codex", 10, 11, 1),
			publishedDirectory(".codex/skills", 11, 12, 2),
		},
	}
}

func publishedDirectory(
	target string,
	parentInode uint64,
	entryInode uint64,
	nameSuffix uint64,
) JournalDirectory {
	return JournalDirectory{
		Target:      DirectoryTarget{Root: domain.RootCodexConfig, Path: target},
		Mode:        0o700,
		Parent:      testIdentity(1, parentInode),
		PrivateName: ".mainframe-" + fixedHex(nameSuffix),
		Entry:       testIdentity(1, entryInode),
		Phase:       StepPublished,
	}
}

func fixedHex(value uint64) string {
	const digits = "00000000000000000000000000000000"
	text := []byte(digits)
	for index := len(text) - 1; value > 0; index-- {
		text[index] = "0123456789abcdef"[value&0xf]
		value >>= 4
	}
	return string(text)
}
