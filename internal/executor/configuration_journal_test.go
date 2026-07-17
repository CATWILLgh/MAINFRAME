package executor

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestPreviewCarriesPreparedConfiguration(t *testing.T) {
	preview := Preview{Configuration: configuration.PreparedPlan{}}
	if !reflect.DeepEqual(preview.Configuration, configuration.PreparedPlan{}) {
		t.Fatalf("configuration = %#v", preview.Configuration)
	}
}

func TestValidatePreparedTargetsAcceptsAnEmptyConfigurationFile(t *testing.T) {
	plan, err := configuration.NewPreparedPlan([]configuration.Transition{{
		ResourceIDs: []string{"codex.mcp.context7"},
		Mutations: []configuration.FileMutation{{
			Target: testLocation("config.toml"),
			Before: configuration.BeforeImage{
				Exists: true, SHA256: testDigest("managed block"), Mode: 0o600,
				Device: 1, Inode: 2,
			},
			After: []byte{}, Mode: 0o600,
		}},
	}})
	if err != nil {
		t.Fatal(err)
	}
	if err := validatePreparedTargets(plan.Transitions(), nil); err != nil {
		t.Fatalf("validatePreparedTargets() rejected an empty file: %v", err)
	}
}

func TestValidateJournalAcceptsConfigurationLifecyclePhases(t *testing.T) {
	tests := []Journal{
		configurationJournalFixture(StepPrepared, TransactionInProgress),
		configurationJournalFixture(StepParentBound, TransactionInProgress),
		configurationJournalFixture(StepPrivateCreated, TransactionInProgress),
		configurationJournalFixture(StepStaged, TransactionInProgress),
		configurationJournalFixture(StepPublished, TransactionCommitted),
		configurationJournalFixture(StepRolledBack, TransactionInProgress),
	}
	for _, journal := range tests {
		if err := validateJournal(journal); err != nil {
			t.Fatalf("validateJournal(%q) error = %v", journal.Configurations[0].Mutations[0].Phase, err)
		}
	}
}

func TestValidateJournalRejectsInvalidConfigurationState(t *testing.T) {
	for _, test := range invalidConfigurationJournalCases() {
		t.Run(test.name, func(t *testing.T) {
			journal := configurationJournalFixture(StepPrepared, TransactionInProgress)
			test.mutate(&journal)
			if err := validateJournal(journal); err == nil {
				t.Fatal("validateJournal() accepted invalid configuration state")
			}
		})
	}
}

type invalidConfigurationJournalCase struct {
	name   string
	mutate func(*Journal)
}

func invalidConfigurationJournalCases() []invalidConfigurationJournalCase {
	return append(
		invalidConfigurationStructureCases(),
		invalidConfigurationMutationCases()...,
	)
}

func invalidConfigurationStructureCases() []invalidConfigurationJournalCase {
	return []invalidConfigurationJournalCase{
		{name: "unsupported schema", mutate: func(journal *Journal) {
			journal.SchemaVersion = 3
		}},
		{name: "empty resource IDs", mutate: func(journal *Journal) {
			journal.Configurations[0].ResourceIDs = nil
		}},
		{name: "invalid resource ID", mutate: func(journal *Journal) {
			journal.Configurations[0].ResourceIDs = []string{"Bad ID"}
		}},
		{name: "duplicate resource ID", mutate: func(journal *Journal) {
			journal.Configurations[0].ResourceIDs = []string{"opencode.permissions", "opencode.permissions"}
		}},
		{name: "empty mutations", mutate: func(journal *Journal) {
			journal.Configurations[0].Mutations = nil
		}},
		{name: "duplicate configuration target", mutate: func(journal *Journal) {
			mutation := journal.Configurations[0].Mutations[0]
			journal.Configurations[0].Mutations = append(
				journal.Configurations[0].Mutations,
				mutation,
			)
		}},
		{name: "overlap with link target", mutate: func(journal *Journal) {
			journal.Plan.Operations = []domain.Operation{install("config.json", "source/config")}
			journal.Steps = []JournalMutation{installJournalStep("config.json", StepPrepared)}
		}},
		{name: "duplicate private name with link", mutate: func(journal *Journal) {
			step := installJournalStep("link", StepPrepared)
			step.Private.Name = journal.Configurations[0].Mutations[0].Private.Name
			journal.Plan.Operations = []domain.Operation{install("link", "source/link")}
			journal.Steps = []JournalMutation{step}
		}},
		{name: "committed prepared mutation", mutate: func(journal *Journal) {
			journal.Status = TransactionCommitted
		}},
	}
}

func invalidConfigurationMutationCases() []invalidConfigurationJournalCase {
	return []invalidConfigurationJournalCase{
		{name: "invalid target", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Target.Path = "../escape"
		})},
		{name: "invalid before digest", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Before.SHA256 = "ABC"
		})},
		{name: "unsafe after mode", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.After.Mode = 0o644
		})},
		{name: "after mode is not readable", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.After.Mode = 0o200
		})},
		{name: "invalid private name", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Private.Name = "temporary"
		})},
		{name: "wrong staged name", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.StagedName = "payload"
		})},
		{name: "prepared staged identity", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.StagedIdentity = FileIdentity{Device: 1, Inode: 9}
		})},
		{name: "parent-bound published identity", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			setConfigurationPhase(mutation, StepParentBound)
			mutation.After.Entry = FileIdentity{Device: 1, Inode: 9}
		})},
		{name: "staged missing identities", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Phase = StepStaged
		})},
		{name: "finalized pre-private rollback has staged identity", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Phase = StepRolledBack
			mutation.Finalized = true
			mutation.StagedIdentity = FileIdentity{Device: 1, Inode: 9}
		})},
		{name: "published identity mismatch", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			setConfigurationPhase(mutation, StepPublished)
			mutation.After.Entry = FileIdentity{Device: 2, Inode: 99}
		})},
		{name: "finalized prepared mutation", mutate: mutateConfiguration(func(mutation *JournalConfigurationMutation) {
			mutation.Finalized = true
		})},
	}
}

func mutateConfiguration(
	mutate func(*JournalConfigurationMutation),
) func(*Journal) {
	return func(journal *Journal) {
		mutate(&journal.Configurations[0].Mutations[0])
	}
}

func configurationJournalFixture(
	phase StepPhase,
	status TransactionStatus,
) Journal {
	mutation := JournalConfigurationMutation{
		Target: testLocation("config.json"),
		Before: ConfigurationFileImage{
			Exists: true, SHA256: testDigest("before"), Mode: 0o644,
			Entry: FileIdentity{Device: 1, Inode: 2},
		},
		After: ConfigurationFileImage{
			Exists: true, SHA256: testDigest("after"), Mode: 0o600,
		},
		Private:    PrivateDirectory{Name: ".mainframe-" + testDigest("config")[:32]},
		StagedName: "staged",
		Phase:      phase,
	}
	setConfigurationPhase(&mutation, phase)
	return Journal{
		SchemaVersion: CurrentJournalSchemaVersion,
		Release: ReleaseIdentity{
			ID: "release", IndexSHA256: testDigest("release"),
		},
		Desired: []domain.ComponentID{"opencode"},
		Status:  status,
		Plan:    domain.Plan{Operations: []domain.Operation{}},
		Roots: []RootSnapshot{{
			Root:           domain.RootCodexConfig,
			AnchorPath:     "/home/user",
			AnchorIdentity: FileIdentity{Device: 1, Inode: 1},
			RootPath:       ".codex-config",
		}},
		Configurations: []JournalConfigurationTransition{{
			ResourceIDs: []string{"opencode.permissions"},
			Mutations:   []JournalConfigurationMutation{mutation},
		}},
		Directories: []JournalDirectory{},
		Steps:       []JournalMutation{},
	}
}

func setConfigurationPhase(
	mutation *JournalConfigurationMutation,
	phase StepPhase,
) {
	mutation.Phase = phase
	if phase == StepPrepared {
		return
	}
	mutation.Parent = FileIdentity{Device: 1, Inode: 3}
	if phase == StepParentBound {
		return
	}
	mutation.Private.Identity = FileIdentity{Device: 1, Inode: 4}
	if phase == StepPrivateCreated {
		return
	}
	mutation.StagedIdentity = FileIdentity{Device: 1, Inode: 5}
	if phase == StepPublished {
		mutation.After.Entry = mutation.StagedIdentity
	}
}

func digestString(value string) string {
	return fmt.Sprintf("%x", sha256.Sum256([]byte(value)))
}

func mutateJournalJSON(
	t *testing.T,
	source []byte,
	mutate func(map[string]any),
) []byte {
	t.Helper()
	var root map[string]any
	if err := json.Unmarshal(source, &root); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}
	mutate(root)
	payload, err := json.Marshal(root)
	if err != nil {
		t.Fatalf("encode mutation: %v", err)
	}
	return payload
}

func firstConfigurationMutation(root map[string]any) map[string]any {
	configurations := root["configurations"].([]any)
	transition := configurations[0].(map[string]any)
	mutations := transition["mutations"].([]any)
	return mutations[0].(map[string]any)
}

func sortStrings(values []string) {
	for index := 1; index < len(values); index++ {
		for current := index; current > 0 && values[current] < values[current-1]; current-- {
			values[current], values[current-1] = values[current-1], values[current]
		}
	}
}
