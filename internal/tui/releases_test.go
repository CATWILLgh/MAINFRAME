package tui

import (
	"strings"
	"testing"
)

type fakeReleaseLister struct {
	summaries []ReleaseSummary
	err       error
	calls     int
}

func (fake *fakeReleaseLister) List() ([]ReleaseSummary, error) {
	fake.calls++
	if fake.err != nil {
		return nil, fake.err
	}
	return append([]ReleaseSummary(nil), fake.summaries...), nil
}

type fakeReleaseReviewer struct {
	review ReleaseReview
	err    error
	calls  int
	lastOp string
}

func (fake *fakeReleaseReviewer) ReviewImport(sourcePath string) (ReleaseReview, error) {
	fake.calls++
	fake.lastOp = "import:" + sourcePath
	if fake.err != nil {
		return ReleaseReview{}, fake.err
	}
	return fake.review, nil
}

func (fake *fakeReleaseReviewer) ReviewActivateCached(
	releaseID, indexSHA256 string,
) (ReleaseReview, error) {
	fake.calls++
	fake.lastOp = "activate:" + releaseID + ":" + indexSHA256
	if fake.err != nil {
		return ReleaseReview{}, fake.err
	}
	return fake.review, nil
}

type fakeReleaseApplier struct {
	err           error
	calls         int
	capturedReview ReleaseReview
}

func (fake *fakeReleaseApplier) Apply(review ReleaseReview) error {
	fake.calls++
	fake.capturedReview = review
	return fake.err
}

func newReleaseTestModel(
	t *testing.T,
	state ReleaseState,
) *Model {
	t.Helper()
	model := NewModel(&fakePreviewer{targets: defaultTargets()}, testCatalog(t), nil)
	model.releases = state
	return model
}

func applicableReleaseReview(
	targetID, targetSHA string, applicable bool,
) ReleaseReview {
	return ReleaseReview{
		Target: ReleaseIdentity{
			ReleaseID: targetID, IndexSHA256: targetSHA,
		},
		Applicable:   applicable,
		Operations:   []ReleaseOperation{{ComponentID: "mainframe-cli", Kind: "replace"}},
		Notices:      []string{"Local release hashes verify integrity, not publisher identity."},
	}.WithApplyRequest(
		[]byte(`{"schema_version":1,"kind":"mainframe-release-apply","operation":"activate-cached","release_id":"`+targetID+`","index_sha256":"`+targetSHA+`"}`),
		"sha256:"+strings.Repeat("0", 64),
	)
}

func TestReleaseScreenRendersEmptyMessageWhenNoCache(t *testing.T) {
	lister := &fakeReleaseLister{summaries: nil}
	model := newReleaseTestModel(t, ReleaseState{Lister: lister})
	model.openReleases()

	if model.screen != screenReleases {
		t.Fatalf("screen = %v, want screenReleases", model.screen)
	}
	if lister.calls != 1 {
		t.Fatalf("Lister.List calls = %d, want 1", lister.calls)
	}
	content := model.View().Content
	if !strings.Contains(content, "No cached releases") {
		t.Fatalf("empty list view missing notice; got %q", content)
	}
}

func TestReleaseScreenListsCachedReleasesWithActiveMarker(t *testing.T) {
	lister := &fakeReleaseLister{summaries: []ReleaseSummary{
		{ReleaseID: "alpha", IndexSHA256: strings.Repeat("a", 64), Active: true},
		{ReleaseID: "beta", IndexSHA256: strings.Repeat("b", 64)},
	}}
	model := newReleaseTestModel(t, ReleaseState{Lister: lister})
	model.openReleases()

	content := model.View().Content
	if !strings.Contains(content, "alpha") || !strings.Contains(content, "[active]") {
		t.Fatalf("list view missing active alpha; got %q", content)
	}
	if !strings.Contains(content, "beta") {
		t.Fatalf("list view missing beta; got %q", content)
	}
}

func TestReleaseScreenActivateFlowAppliesByteIdenticalReview(t *testing.T) {
	targetSHA := strings.Repeat("c", 64)
	lister := &fakeReleaseLister{summaries: []ReleaseSummary{
		{ReleaseID: "alpha", IndexSHA256: targetSHA},
	}}
	review := applicableReleaseReview("alpha", targetSHA, true)
	reviewer := &fakeReleaseReviewer{review: review}
	applier := &fakeReleaseApplier{}
	model := newReleaseTestModel(t, ReleaseState{
		Lister: lister, Reviewer: reviewer, Applier: applier,
	})
	model.openReleases()

	model.releaseMenuChoice = releaseMenuChoice("activate:alpha:" + targetSHA)
	model.continueFromReleases()

	if model.screen != screenReleaseConfirm {
		t.Fatalf("screen = %v, want screenReleaseConfirm", model.screen)
	}
	if reviewer.calls != 1 || reviewer.lastOp != "activate:alpha:"+targetSHA {
		t.Fatalf("reviewer called %d times, lastOp=%q", reviewer.calls, reviewer.lastOp)
	}
	if model.activeReleaseReview == nil ||
		model.activeReleaseReview.Confirmation() != review.Confirmation() {
		t.Fatalf("active review confirmation lost")
	}

	model.applyConfirmed = true
	model.continueFromReleaseConfirm()

	if applier.calls != 1 {
		t.Fatalf("Applier.Apply calls = %d, want 1", applier.calls)
	}
	if applier.capturedReview.Confirmation() != review.Confirmation() {
		t.Fatalf("applier received confirmation %q, want %q (byte-identical round-trip)",
			applier.capturedReview.Confirmation(), review.Confirmation())
	}
	if !model.releaseApplied {
		t.Fatalf("releaseApplied = false, want true")
	}
	if !strings.Contains(model.releaseAppliedNotice, "Restart MAINFRAME") {
		t.Fatalf("missing restart notice; got %q", model.releaseAppliedNotice)
	}
	if model.screen != screenReleases {
		t.Fatalf("screen = %v, want screenReleases (return to list, no dead-end)",
			model.screen)
	}
}

func TestReleaseScreenActivateFlowWithoutConfirmationReturnsToList(t *testing.T) {
	targetSHA := strings.Repeat("d", 64)
	lister := &fakeReleaseLister{summaries: []ReleaseSummary{
		{ReleaseID: "beta", IndexSHA256: targetSHA},
	}}
	reviewer := &fakeReleaseReviewer{
		review: applicableReleaseReview("beta", targetSHA, true),
	}
	applier := &fakeReleaseApplier{}
	model := newReleaseTestModel(t, ReleaseState{
		Lister: lister, Reviewer: reviewer, Applier: applier,
	})
	model.openReleases()
	model.releaseMenuChoice = releaseMenuChoice("activate:beta:" + targetSHA)
	model.continueFromReleases()
	model.applyConfirmed = false
	model.continueFromReleaseConfirm()

	if applier.calls != 0 {
		t.Fatalf("Applier.Apply calls = %d, want 0 on cancelled confirm", applier.calls)
	}
	if model.screen != screenReleases {
		t.Fatalf("screen = %v, want screenReleases", model.screen)
	}
}

func TestReleaseScreenRecoveryRequiredDoesNotApply(t *testing.T) {
	targetSHA := strings.Repeat("e", 64)
	lister := &fakeReleaseLister{summaries: []ReleaseSummary{
		{ReleaseID: "gamma", IndexSHA256: targetSHA},
	}}
	review := applicableReleaseReview("gamma", targetSHA, false)
	review.RecoveryRequired = true
	review = review.WithApplyRequest(nil, "")
	reviewer := &fakeReleaseReviewer{review: review}
	applier := &fakeReleaseApplier{}
	model := newReleaseTestModel(t, ReleaseState{
		Lister: lister, Reviewer: reviewer, Applier: applier,
	})
	model.openReleases()
	model.releaseMenuChoice = releaseMenuChoice("activate:gamma:" + targetSHA)
	model.continueFromReleases()

	if model.activeReleaseReview == nil || !model.activeReleaseReview.RecoveryRequired {
		t.Fatalf("recovery review not surfaced; active=%v", model.activeReleaseReview)
	}
	content := model.View().Content
	if !strings.Contains(content, "Recovery required") {
		t.Fatalf("recovery notice missing in confirm view; got %q", content)
	}
	model.applyConfirmed = true
	model.continueFromReleaseConfirm()
	if applier.calls != 0 {
		t.Fatalf("Applier.Apply calls = %d, want 0 (recovery review has no apply target)",
			applier.calls)
	}
}

func TestReleaseScreenImportFlowReviewsPathAndApplies(t *testing.T) {
	targetSHA := strings.Repeat("f", 64)
	review := applicableReleaseReview("imported", targetSHA, true)
	reviewer := &fakeReleaseReviewer{review: review}
	applier := &fakeReleaseApplier{}
	model := newReleaseTestModel(t, ReleaseState{
		Lister:   &fakeReleaseLister{},
		Reviewer: reviewer, Applier: applier,
	})
	model.openReleases()
	model.releaseMenuChoice = releaseMenuImport
	model.continueFromReleases()

	if model.screen != screenReleaseImport {
		t.Fatalf("screen = %v, want screenReleaseImport", model.screen)
	}
	model.releaseImportPath = "/tmp/release-source"
	model.continueFromReleaseImport()

	if reviewer.calls != 1 || reviewer.lastOp != "import:/tmp/release-source" {
		t.Fatalf("reviewer called %d, lastOp=%q", reviewer.calls, reviewer.lastOp)
	}
	if model.screen != screenReleaseConfirm {
		t.Fatalf("screen = %v, want screenReleaseConfirm", model.screen)
	}
	model.applyConfirmed = true
	model.continueFromReleaseConfirm()
	if applier.calls != 1 {
		t.Fatalf("Applier.Apply calls = %d, want 1", applier.calls)
	}
}

func TestReleaseScreenReviewErrorReturnsToList(t *testing.T) {
	lister := &fakeReleaseLister{summaries: []ReleaseSummary{
		{ReleaseID: "alpha", IndexSHA256: strings.Repeat("a", 64)},
	}}
	reviewer := &fakeReleaseReviewer{err: errReleaseFake()}
	model := newReleaseTestModel(t, ReleaseState{
		Lister: lister, Reviewer: reviewer,
	})
	model.openReleases()
	model.releaseMenuChoice = releaseMenuChoice("activate:alpha:" + strings.Repeat("a", 64))
	model.continueFromReleases()

	if model.screen != screenReleases {
		t.Fatalf("screen = %v, want screenReleases (error returns to list)", model.screen)
	}
	if reviewer.calls != 1 {
		t.Fatalf("reviewer calls = %d, want 1", reviewer.calls)
	}
}

type fakeReleaseError struct{ msg string }

func (err fakeReleaseError) Error() string { return err.msg }

func errReleaseFake() error {
	return fakeReleaseError{msg: "release review simulated failure"}
}
