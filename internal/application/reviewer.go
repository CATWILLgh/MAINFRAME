package application

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
)

type Reviewer struct {
	snapshots SnapshotBuilder
}

func NewReviewer(snapshots SnapshotBuilder) (Reviewer, error) {
	if snapshots == nil {
		return Reviewer{}, errors.New("snapshot builder must not be nil")
	}
	return Reviewer{snapshots: snapshots}, nil
}

func (reviewer Reviewer) Preview(request Request) (lifecycle.Preview, error) {
	_, _, semantic, err := buildSemanticPreview(
		reviewer.snapshots,
		cloneRequest(request),
	)
	if err != nil {
		return lifecycle.Preview{}, fmt.Errorf(
			"review installation plan: %w",
			err,
		)
	}
	return cloneSemantic(semantic), nil
}

func (reviewer Reviewer) Review(request Request) (ReviewedPlan, error) {
	reviewed, err := buildReviewedPlan(reviewer.snapshots, cloneRequest(request))
	if err != nil {
		return ReviewedPlan{}, fmt.Errorf("review installation plan: %w", err)
	}
	return reviewed, nil
}

func buildSemanticPreview(
	snapshots SnapshotBuilder,
	request Request,
) (Snapshot, lifecycle.PreviewRequest, lifecycle.Preview, error) {
	snapshot, err := snapshots.Build(cloneRequest(request))
	if err != nil {
		return Snapshot{}, lifecycle.PreviewRequest{}, lifecycle.Preview{},
			fmt.Errorf("build fresh host snapshot: %w", err)
	}
	lifecycleRequest, err := buildLifecycleRequest(snapshot, request)
	if err != nil {
		return Snapshot{}, lifecycle.PreviewRequest{}, lifecycle.Preview{}, err
	}
	semantic, err := snapshot.Lifecycle.Preview(lifecycleRequest)
	if err != nil {
		return Snapshot{}, lifecycle.PreviewRequest{}, lifecycle.Preview{},
			fmt.Errorf("build semantic preview: %w", err)
	}
	return snapshot, lifecycleRequest, semantic, nil
}
