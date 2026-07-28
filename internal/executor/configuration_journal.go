package executor

import (
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

const CurrentJournalSchemaVersion = 4

type ConfigurationMutationDisposition string

const (
	ConfigurationPresent             ConfigurationMutationDisposition = "present"
	ConfigurationRemoveExactDocument ConfigurationMutationDisposition = "remove_exact_document"
	ConfigurationRemoveManagedSecret ConfigurationMutationDisposition = "remove_managed_secret"
)

type ConfigurationFileImage struct {
	Exists bool         `json:"exists"`
	SHA256 string       `json:"sha256"`
	Mode   uint32       `json:"mode"`
	Entry  FileIdentity `json:"entry"`
}

type ConfigurationState struct {
	Exists bool
	SHA256 string
	Mode   uint32
	Parent FileIdentity
	Entry  FileIdentity
}

type ConfigurationWorkspace interface {
	CheckReadPrecondition(configuration.ReadPrecondition) error
	InspectConfiguration(domain.Location) (ConfigurationState, error)
	PrepareConfigurationPrivate(JournalConfigurationMutation) (FileIdentity, error)
	CheckConfigurationCapabilities(JournalConfigurationMutation) error
	StageConfiguration(JournalConfigurationMutation, []byte) (FileIdentity, error)
	AdoptStagedConfiguration(JournalConfigurationMutation) (FileIdentity, bool, error)
	PublishConfiguration(JournalConfigurationMutation) (ConfigurationState, error)
	RollbackConfiguration(JournalConfigurationMutation) error
	FinalizeConfiguration(JournalConfigurationMutation) error
	FinalizeConfigurationPrivate(JournalConfigurationMutation) error
}

type JournalConfigurationMutation struct {
	Disposition    ConfigurationMutationDisposition `json:"disposition"`
	Target         domain.Location                  `json:"target"`
	Before         ConfigurationFileImage           `json:"before"`
	After          ConfigurationFileImage           `json:"after"`
	Parent         FileIdentity                     `json:"parent"`
	Private        PrivateDirectory                 `json:"private"`
	StagedName     string                           `json:"staged_name"`
	StagedIdentity FileIdentity                     `json:"staged_identity"`
	Phase          StepPhase                        `json:"phase"`
	Finalized      bool                             `json:"finalized"`
}

type JournalConfigurationTransition struct {
	ResourceIDs []string                       `json:"resource_ids"`
	Mutations   []JournalConfigurationMutation `json:"mutations"`
}

func cloneJournalConfigurations(
	source []JournalConfigurationTransition,
) []JournalConfigurationTransition {
	result := make([]JournalConfigurationTransition, len(source))
	for index, transition := range source {
		result[index] = JournalConfigurationTransition{
			ResourceIDs: append([]string(nil), transition.ResourceIDs...),
			Mutations: append(
				[]JournalConfigurationMutation(nil),
				transition.Mutations...,
			),
		}
	}
	return result
}
