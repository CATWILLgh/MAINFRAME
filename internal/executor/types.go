package executor

import (
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

type ReleaseIdentity struct {
	ID          string `json:"id"`
	IndexSHA256 string `json:"index_sha256"`
}

type Preview struct {
	Release       ReleaseIdentity
	Desired       []domain.ComponentID
	Plan          domain.Plan
	Configuration configuration.PreparedPlan
}

type Result struct {
	Warnings  []string
	Recovered bool
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

type OwnershipStore interface {
	LoadOwnership() (linkownership.Registry, error)
	SaveOwnership(linkownership.Registry) error
}

type Refresher interface {
	Refresh([]domain.ComponentID) (Preview, error)
}

type LinkWorkspace interface {
	Inspect(domain.Location) (LinkState, error)
	ResolveSource(domain.ArtifactPath) (string, error)
	PlanDirectories(domain.Plan) (DirectoryPlan, error)
	CheckDirectoryMode(uint32) error
	AllocatePrivateName() (string, error)
	InspectDirectory(DirectoryMutation) (DirectoryState, error)
	StageDirectory(DirectoryMutation) (FileIdentity, error)
	PublishDirectory(DirectoryMutation) (DirectoryState, error)
	RollbackDirectory(DirectoryMutation) error
	FinalizeDirectory(DirectoryMutation) error
	PreparePrivate(WorkspaceMutation) (FileIdentity, error)
	StageInstall(WorkspaceMutation) (FileIdentity, error)
	PublishInstall(WorkspaceMutation) (LinkState, error)
	PublishReplace(WorkspaceMutation) (LinkState, error)
	PublishRemove(WorkspaceMutation) (LinkState, error)
	Rollback(WorkspaceMutation) error
	Finalize(WorkspaceMutation) error
	FinalizePrivate(WorkspaceMutation) error
}

type FileIdentity struct {
	Device           uint64 `json:"device"`
	Inode            uint64 `json:"inode"`
	BirthSeconds     int64  `json:"birth_seconds"`
	BirthNanoseconds int64  `json:"birth_nanoseconds"`
}

const ManagedDirectoryMode uint32 = 0o700

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

type RootSnapshot struct {
	Root           domain.RootID `json:"root"`
	AnchorPath     string        `json:"anchor_path"`
	AnchorIdentity FileIdentity  `json:"anchor_identity"`
	RootPath       string        `json:"root_path"`
}

type DirectoryTarget struct {
	Root domain.RootID `json:"root"`
	Path string        `json:"path"`
}

type DirectoryRequirement struct {
	Target DirectoryTarget `json:"target"`
	Mode   uint32          `json:"mode"`
}

type DirectoryPlan struct {
	Roots   []RootSnapshot
	Missing []DirectoryRequirement
}

type DirectoryState struct {
	Exists bool
	Parent FileIdentity
	Entry  FileIdentity
	Mode   uint32
}

type MutationKind string

const (
	MutationInstall    MutationKind = "install"
	MutationAdopt      MutationKind = "adopt"
	MutationReplace    MutationKind = "replace"
	MutationRemove     MutationKind = "remove"
	MutationRelinquish MutationKind = "relinquish"
)

type StepPhase string

const (
	StepPrepared       StepPhase = "prepared"
	StepParentBound    StepPhase = "parent_bound"
	StepPrivateCreated StepPhase = "private_created"
	StepStaged         StepPhase = "staged"
	StepPublished      StepPhase = "published"
	StepRolledBack     StepPhase = "rolled_back"
)

type TransactionStatus string

const (
	TransactionInProgress TransactionStatus = "in_progress"
	TransactionCommitted  TransactionStatus = "committed"
)

type JournalMutation struct {
	ComponentID     domain.ComponentID     `json:"component_id,omitempty"`
	UnitID          string                 `json:"unit_id,omitempty"`
	Kind            MutationKind           `json:"kind"`
	Location        domain.Location        `json:"location"`
	SourcePath      domain.ArtifactPath    `json:"source_path"`
	SourceSHA256    string                 `json:"source_sha256,omitempty"`
	Materialization domain.Materialization `json:"materialization,omitempty"`
	Before          LinkImage              `json:"before"`
	After           LinkImage              `json:"after"`
	FileBefore      ConfigurationFileImage `json:"file_before,omitempty"`
	FileAfter       ConfigurationFileImage `json:"file_after,omitempty"`
	Parent          FileIdentity           `json:"parent"`
	Private         PrivateDirectory       `json:"private"`
	StagedName      string                 `json:"staged_name"`
	StagedIdentity  FileIdentity           `json:"staged_identity"`
	RetainedName    string                 `json:"retained_name"`
	Phase           StepPhase              `json:"phase"`
	Finalized       bool                   `json:"finalized"`
	ClaimBefore     *linkownership.Claim   `json:"claim_before,omitempty"`
	ClaimAfter      *linkownership.Claim   `json:"claim_after,omitempty"`
	ClaimPhase      ClaimPhase             `json:"claim_phase,omitempty"`
}

type ClaimPhase string

const (
	ClaimPrepared   ClaimPhase = "prepared"
	ClaimPublished  ClaimPhase = "published"
	ClaimRolledBack ClaimPhase = "rolled_back"
)

type JournalDirectory struct {
	Target      DirectoryTarget `json:"target"`
	Mode        uint32          `json:"mode"`
	Parent      FileIdentity    `json:"parent"`
	PrivateName string          `json:"private_name"`
	Entry       FileIdentity    `json:"entry"`
	Phase       StepPhase       `json:"phase"`
	Finalized   bool            `json:"finalized"`
}

type DirectoryMutation struct {
	Root        RootSnapshot
	Target      DirectoryTarget
	Mode        uint32
	Parent      FileIdentity
	PrivateName string
	Entry       FileIdentity
	Phase       StepPhase
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
	SchemaVersion  int                              `json:"schema_version"`
	Release        ReleaseIdentity                  `json:"release"`
	Desired        []domain.ComponentID             `json:"desired"`
	Status         TransactionStatus                `json:"status"`
	Plan           domain.Plan                      `json:"plan"`
	Roots          []RootSnapshot                   `json:"roots"`
	Configurations []JournalConfigurationTransition `json:"configurations"`
	Directories    []JournalDirectory               `json:"directories"`
	Steps          []JournalMutation                `json:"steps"`
}

func cloneJournalPointer(journal *Journal) *Journal {
	if journal == nil {
		return nil
	}
	clone := *journal
	clone.Desired = append([]domain.ComponentID(nil), journal.Desired...)
	clone.Plan.Operations = append([]domain.Operation(nil), journal.Plan.Operations...)
	clone.Roots = append([]RootSnapshot(nil), journal.Roots...)
	clone.Configurations = cloneJournalConfigurations(journal.Configurations)
	clone.Directories = append([]JournalDirectory(nil), journal.Directories...)
	clone.Steps = append([]JournalMutation(nil), journal.Steps...)
	for index := range clone.Steps {
		clone.Steps[index].ClaimBefore = cloneClaim(clone.Steps[index].ClaimBefore)
		clone.Steps[index].ClaimAfter = cloneClaim(clone.Steps[index].ClaimAfter)
	}
	return &clone
}

func cloneClaim(claim *linkownership.Claim) *linkownership.Claim {
	if claim == nil {
		return nil
	}
	cloned := *claim
	return &cloned
}
