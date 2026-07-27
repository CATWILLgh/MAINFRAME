package application

import "testing"

func TestConfirmedRefreshRejectsFreshPlanThatIsNoLongerApplicable(
	t *testing.T,
) {
	snapshot := testSnapshot(t)
	builder := &fakeSnapshotBuilder{snapshots: []Snapshot{snapshot, snapshot}}
	session := &fakeApplySession{refresh: true}
	service, err := New(
		builder,
		&fakeApplyExecutorFactory{session: session},
		readyRecoveryFactory(),
	)
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	reviewed, err := service.Review(testRequest())
	if err != nil {
		t.Fatalf("Review() error = %v", err)
	}
	reviewed.applicable = true

	if _, err := service.ApplyConfirmed(reviewed); err == nil {
		t.Fatal("ApplyConfirmed() accepted a freshly inapplicable plan")
	}
	if session.nonRecoveringApplies != 1 || session.applies != 0 {
		t.Fatalf(
			"non-recovering/recovering applies = %d/%d",
			session.nonRecoveringApplies,
			session.applies,
		)
	}
}
