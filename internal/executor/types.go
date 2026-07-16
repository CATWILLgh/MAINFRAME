package executor

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

type ReleaseIdentity struct {
	ID          string `json:"id"`
	IndexSHA256 string `json:"index_sha256"`
}

type Preview struct {
	Release ReleaseIdentity
	Desired []domain.ComponentID
	Plan    domain.Plan
}

type Result struct {
	Warnings []string
}

type Lock interface {
	Unlock() error
}

type Locker interface {
	Lock() (Lock, error)
}

type JournalStore interface {
	Load() (*Journal, error)
	Save(Journal) error
	Cleanup() error
}

type Refresher interface {
	Refresh([]domain.ComponentID) (Preview, error)
}

type LinkWorkspace interface {
	Inspect(domain.Location) (LinkState, error)
	ResolveSource(domain.ArtifactPath) (string, error)
	AllocatePrivateName() (string, error)
	PreparePrivate(WorkspaceMutation) (FileIdentity, error)
	StageInstall(WorkspaceMutation) (FileIdentity, error)
	PublishInstall(WorkspaceMutation) (LinkState, error)
	PublishRemove(WorkspaceMutation) (LinkState, error)
	Rollback(WorkspaceMutation) error
	Finalize(WorkspaceMutation) error
	FinalizePrivate(WorkspaceMutation) error
}

type FileIdentity struct {
	Device uint64 `json:"device"`
	Inode  uint64 `json:"inode"`
}

type LinkImage struct {
	Exists    bool         `json:"exists"`
	RawTarget string       `json:"raw_target"`
	Entry     FileIdentity `json:"entry"`
}

type LinkState struct {
	Exists    bool
	RawTarget string
	Parent    FileIdentity
	Entry     FileIdentity
}

type PrivateDirectory struct {
	Name     string       `json:"name"`
	Identity FileIdentity `json:"identity"`
}

type MutationKind string

const (
	MutationInstall MutationKind = "install"
	MutationRemove  MutationKind = "remove"
)

type StepPhase string

const (
	StepPrepared   StepPhase = "prepared"
	StepStaged     StepPhase = "staged"
	StepPublished  StepPhase = "published"
	StepRolledBack StepPhase = "rolled_back"
)

type TransactionStatus string

const (
	TransactionInProgress TransactionStatus = "in_progress"
	TransactionCommitted  TransactionStatus = "committed"
)

type JournalMutation struct {
	Kind           MutationKind        `json:"kind"`
	Location       domain.Location     `json:"location"`
	SourcePath     domain.ArtifactPath `json:"source_path,omitempty"`
	Before         LinkImage           `json:"before"`
	After          LinkImage           `json:"after"`
	Parent         FileIdentity        `json:"parent"`
	Private        PrivateDirectory    `json:"private"`
	StagedName     string              `json:"staged_name"`
	StagedIdentity FileIdentity        `json:"staged_identity"`
	RetainedName   string              `json:"retained_name"`
	Phase          StepPhase           `json:"phase"`
	Finalized      bool                `json:"finalized"`
}

type WorkspaceMutation struct {
	Kind           MutationKind
	Location       domain.Location
	SourceTarget   string
	Before         LinkImage
	After          LinkImage
	Parent         FileIdentity
	Private        PrivateDirectory
	StagedName     string
	StagedIdentity FileIdentity
	RetainedName   string
	Phase          StepPhase
}

type Journal struct {
	Release ReleaseIdentity      `json:"release"`
	Desired []domain.ComponentID `json:"desired"`
	Status  TransactionStatus    `json:"status"`
	Steps   []JournalMutation    `json:"steps"`
}

func cloneJournalPointer(journal *Journal) *Journal {
	if journal == nil {
		return nil
	}
	clone := *journal
	clone.Desired = append([]domain.ComponentID(nil), journal.Desired...)
	clone.Steps = append([]JournalMutation(nil), journal.Steps...)
	return &clone
}
