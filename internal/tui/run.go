package tui

import (
	"fmt"
	"io"

	tea "charm.land/bubbletea/v2"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/credentialmigration"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
)

type CredentialState struct {
	Definitions     credentialcatalog.Definitions
	Instances       credentialcatalog.Instances
	LegacyInspector LegacyIndexInspector
	LegacyPreviewer LegacyReferencePreviewer
	LegacyPlanner   LegacyTransferPlanner
	SecretCreator   SecretCreator
	Recovered       bool
	Warnings        []string
}

type LegacyIndexInspector interface {
	Inspect() ([]credentialmigration.LegacyIndex, error)
}

type LegacyReferencePreviewer interface {
	Preview() (credentialmigration.LegacyReferenceInventory, error)
}

type LegacyTransferPlanner interface {
	Plan() (credentialmigration.LegacyTransferPlan, error)
}

type SecretCreator interface {
	CreateSecret(reference string, value []byte) error
}

type ReleaseSummary struct {
	ReleaseID   string
	IndexSHA256 string
	Active      bool
}

type ReleaseReview struct {
	Target           ReleaseIdentity
	Previous         *ReleaseIdentity
	Operations       []ReleaseOperation
	Applicable       bool
	RecoveryRequired bool
	Notices          []string
	applyRequest     []byte
	confirmation     string
}

type ReleaseIdentity struct {
	ReleaseID   string
	IndexSHA256 string
}

type ReleaseOperation struct {
	ComponentID string
	Kind        string
	SourcePath  string
}

type releaseMenuChoice string

func (review ReleaseReview) ApplyRequest() []byte    { return review.applyRequest }
func (review ReleaseReview) Confirmation() string    { return review.confirmation }
func (review ReleaseReview) HasApplyTarget() bool {
	return review.Applicable && review.applyRequest != nil && review.confirmation != ""
}

type ReleaseLister interface {
	List() ([]ReleaseSummary, error)
}

type ReleaseReviewer interface {
	ReviewImport(sourcePath string) (ReleaseReview, error)
	ReviewActivateCached(releaseID, indexSHA256 string) (ReleaseReview, error)
}

type ReleaseApplier interface {
	Apply(review ReleaseReview) error
}

type ReleaseState struct {
	Lister   ReleaseLister
	Reviewer ReleaseReviewer
	Applier  ReleaseApplier
}

func Run(
	input io.Reader,
	output io.Writer,
	reviewer PlanReviewer,
	catalog mcpcatalog.Catalog,
	stats mcpcatalog.StatsSource,
	credentials CredentialState,
	releases ReleaseState,
) error {
	program := tea.NewProgram(
		NewModelWithReleases(reviewer, catalog, stats, []CredentialState{credentials}, releases),
		tea.WithInput(input),
		tea.WithOutput(output),
	)
	if _, err := program.Run(); err != nil {
		return fmt.Errorf("run terminal preview: %w", err)
	}
	return nil
}
