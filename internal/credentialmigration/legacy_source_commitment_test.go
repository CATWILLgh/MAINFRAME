package credentialmigration

import (
	"io/fs"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestLegacyTransferSourceCommitmentBindsContentAndIdentity(t *testing.T) {
	release := legacyReleaseFixture()
	entries := legacyCommitmentEntries(release)
	first := inspectLegacyCommitment(t, release, entries)

	changedContent := cloneLegacyEntries(entries)
	entry := changedContent[release.Resources[0].Target]
	entry.Content = append(append([]byte(nil), entry.Content...), ' ')
	changedContent[release.Resources[0].Target] = entry
	second := inspectLegacyCommitment(t, release, changedContent)
	if first == second {
		t.Fatal("source commitment ignored content change")
	}

	changedIdentity := cloneLegacyEntries(entries)
	entry = changedIdentity[release.Resources[0].Target]
	entry.Inode++
	changedIdentity[release.Resources[0].Target] = entry
	third := inspectLegacyCommitment(t, release, changedIdentity)
	if first == third {
		t.Fatal("source commitment ignored identity change")
	}
}

func TestLegacyTransferSourceCommitmentIsValueFreeAndDeterministic(
	t *testing.T,
) {
	release := legacyReleaseFixture()
	entries := legacyCommitmentEntries(release)
	first := inspectLegacyCommitment(t, release, entries)
	second := inspectLegacyCommitment(t, release, cloneLegacyEntries(entries))
	if first != second || !strings.HasPrefix(first, "sha256:") {
		t.Fatalf("commitments = %q and %q", first, second)
	}
	for _, entry := range entries {
		if strings.Contains(first, string(entry.Content)) {
			t.Fatalf("commitment exposed source content: %q", first)
		}
	}
}

func inspectLegacyCommitment(
	t *testing.T,
	release releasecontract.Release,
	entries map[domain.Location]hostfs.Entry,
) string {
	t.Helper()
	plan, err := InspectLegacyTransferPlan(
		release,
		&legacyInspectorFixture{
			entries: entries,
			errors: map[domain.Location]error{
				release.Resources[3].Target: fs.ErrNotExist,
			},
		},
	)
	if err != nil {
		t.Fatalf("InspectLegacyTransferPlan() error = %v", err)
	}
	commitment, err := LegacyTransferSourceCommitment(plan)
	if err != nil {
		t.Fatalf("LegacyTransferSourceCommitment() error = %v", err)
	}
	return commitment
}

func legacyCommitmentEntries(
	release releasecontract.Release,
) map[domain.Location]hostfs.Entry {
	entries := make(map[domain.Location]hostfs.Entry, 3)
	for index := 0; index < 3; index++ {
		entries[release.Resources[index].Target] = hostfs.Entry{
			Kind: hostfs.EntryRegular,
			Mode: 0o600,
			Content: []byte(
				"# Catalog\n## Home\nsecret get SHARED_KEY\n",
			),
			Device:           41,
			Inode:            uint64(51 + index),
			BirthSeconds:     61,
			BirthNanoseconds: 71,
		}
	}
	return entries
}

func cloneLegacyEntries(
	source map[domain.Location]hostfs.Entry,
) map[domain.Location]hostfs.Entry {
	result := make(map[domain.Location]hostfs.Entry, len(source))
	for location, entry := range source {
		entry.Content = append([]byte(nil), entry.Content...)
		result[location] = entry
	}
	return result
}
