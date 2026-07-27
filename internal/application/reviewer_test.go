package application

import (
	"reflect"
	"testing"
)

func TestNewReviewerRejectsMissingSnapshotBuilder(t *testing.T) {
	if _, err := NewReviewer(nil); err == nil {
		t.Fatal("NewReviewer() accepted a missing snapshot builder")
	}
}

func TestReviewerBuildsTheSameImmutableReviewWithoutApplyDependencies(
	t *testing.T,
) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	reviewer, err := NewReviewer(builder)
	if err != nil {
		t.Fatalf("NewReviewer() error = %v", err)
	}
	request := testRequest()

	reviewed, err := reviewer.Review(request)
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	request.MCPSelections = nil

	if !reflect.DeepEqual(reviewed.Request(), testRequest()) {
		t.Fatalf("reviewed request = %#v, want %#v", reviewed.Request(), testRequest())
	}
	if len(reviewed.Semantic().Filesystem.Operations) != 1 {
		t.Fatalf("semantic preview = %#v", reviewed.Semantic())
	}
	if builder.builds != 1 {
		t.Fatalf("snapshot builds = %d, want 1", builder.builds)
	}
}

func TestReviewerBuildsSemanticPreviewWithoutExecutablePreparation(t *testing.T) {
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{testSnapshot(t)}}
	reviewer, err := NewReviewer(builder)
	if err != nil {
		t.Fatalf("NewReviewer() error = %v", err)
	}
	request := testRequest()

	preview, err := reviewer.Preview(request)
	if err != nil {
		t.Fatalf("Preview() error = %v", err)
	}
	request.Components = nil

	if len(preview.Filesystem.Operations) != 1 {
		t.Fatalf("semantic preview = %#v", preview)
	}
	if builder.builds != 1 {
		t.Fatalf("snapshot builds = %d, want 1", builder.builds)
	}
}
