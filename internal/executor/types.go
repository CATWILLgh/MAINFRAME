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
	CompareAndSwapLink(domain.Location, LinkState, LinkState) (LinkState, error)
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

type MutationKind string

const (
	MutationInstall MutationKind = "install"
	MutationRemove  MutationKind = "remove"
)

type StepState string

const (
	StepPrepared   StepState = "prepared"
	StepApplied    StepState = "applied"
	StepRolledBack StepState = "rolled_back"
)

type TransactionStatus string

const (
	TransactionInProgress TransactionStatus = "in_progress"
	TransactionCommitted  TransactionStatus = "committed"
)

type JournalMutation struct {
	Kind       MutationKind        `json:"kind"`
	Location   domain.Location     `json:"location"`
	SourcePath domain.ArtifactPath `json:"source_path,omitempty"`
	Before     LinkImage           `json:"before"`
	After      LinkImage           `json:"after"`
	Parent     FileIdentity        `json:"parent"`
	State      StepState           `json:"state"`
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
