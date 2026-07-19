package executor

import (
	"errors"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

func TestApplyInstallsLinkAndOwnershipClaim(t *testing.T) {
	operation := claimedInstall("one", "source/one")
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	claim, exists := fixture.store.ownership.ClaimAt(operation.Artifact.Location)
	if !exists || claim.UnitID != operation.UnitID || claim.RawTarget != "source/one" ||
		claim.ReleaseID != preview.Release.ID || claim.IndexSHA256 != preview.Release.IndexSHA256 {
		t.Fatalf("ownership claim = %#v, exists = %t", claim, exists)
	}
}

func TestApplyReplacesClaimedLinkWithoutAbsentPublicName(t *testing.T) {
	location := testLocation("one")
	oldState := linkState("source/old")
	operation := claimedMutation(domain.OperationReplace, location, oldState, "source/new")
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = oldState
	fixture.store.ownership = registryWith(t, claimFor(operation, "source/old", "old-release", testDigest("old")))

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if got := fixture.workspace.links[location]; !got.Exists || got.RawTarget != "source/new" {
		t.Fatalf("replacement state = %#v", got)
	}
	if fixture.workspace.absentPublicObserved {
		t.Fatal("replacement exposed an absent public link")
	}
	claim, _ := fixture.store.ownership.ClaimAt(location)
	if claim.RawTarget != "source/new" || claim.ReleaseID != "release" {
		t.Fatalf("replacement claim = %#v", claim)
	}
}

func TestApplyAdoptsExactCurrentLinkWithoutReplacingIt(t *testing.T) {
	location := testLocation("one")
	before := linkState("source/current")
	operation := claimedMutation(domain.OperationAdopt, location, before, "")
	operation.Artifact.Ownership = domain.OwnershipExactAdoptable
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.links[location] != before || fixture.workspace.writeCount() != 0 {
		t.Fatalf("adoption changed link: %#v", fixture.workspace.links[location])
	}
	claim, exists := fixture.store.ownership.ClaimAt(location)
	if !exists || claim.UnitID != operation.UnitID || claim.RawTarget != before.RawTarget {
		t.Fatalf("adopted claim = %#v, exists = %t", claim, exists)
	}
}

func TestApplyRollsBackAdoptionWhenLinkChangesDuringClaimPublication(t *testing.T) {
	location := testLocation("one")
	before := linkState("source/one")
	operation := claimedMutation(domain.OperationAdopt, location, before, "")
	operation.Artifact.Ownership = domain.OwnershipExactAdoptable
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before
	foreign := linkState("foreign/one")
	fixture.store.ownershipAfterSave = func() {
		fixture.workspace.links[location] = foreign
		fixture.store.ownershipAfterSave = nil
	}

	if _, err := fixture.executor().Apply(preview); err == nil {
		t.Fatal("Apply() accepted a link changed during adoption")
	}
	if fixture.workspace.links[location] != foreign {
		t.Fatalf("failed adoption changed foreign link: %#v", fixture.workspace.links[location])
	}
	if len(fixture.store.ownership.Claims()) != 0 || fixture.store.journal != nil {
		t.Fatalf(
			"failed adoption left claim or journal: %#v %#v",
			fixture.store.ownership.Claims(), fixture.store.journal,
		)
	}
}

func TestApplyRejectsAdoptionWithoutStableUnitID(t *testing.T) {
	location := testLocation("one")
	before := linkState("source/current")
	operation := domain.Operation{
		ComponentID: "codex", Kind: domain.OperationAdopt,
		Artifact: domain.Artifact{
			Location: location, Ownership: domain.OwnershipExactAdoptable,
			RawTarget:  before.RawTarget,
			LinkDevice: before.Entry.Device, LinkInode: before.Entry.Inode,
		},
	}
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before

	if _, err := fixture.executor().Apply(preview); err == nil {
		t.Fatal("Apply() accepted adoption without stable unit ID")
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("invalid adoption caused writes")
	}
}

func TestApplyRejectsReplacementWithoutStableUnitID(t *testing.T) {
	location := testLocation("one")
	before := linkState("source/old")
	operation := claimedMutation(domain.OperationReplace, location, before, "source/new")
	operation.UnitID = ""
	operation.Artifact.UnitID = ""
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before

	if _, err := fixture.executor().Apply(preview); err == nil {
		t.Fatal("Apply() accepted replacement without stable unit ID")
	}
	if fixture.workspace.writeCount() != 0 || len(fixture.store.saves) != 0 {
		t.Fatal("invalid replacement caused writes")
	}
}

func TestApplyRollsBackFailedAdoptionWithoutChangingLink(t *testing.T) {
	location := testLocation("one")
	before := linkState("source/current")
	operation := claimedMutation(domain.OperationAdopt, location, before, "")
	operation.Artifact.Ownership = domain.OwnershipExactAdoptable
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before
	fixture.store.ownershipFailAfterAt = 1

	if _, err := fixture.executor().Apply(preview); err == nil {
		t.Fatal("Apply() unexpectedly succeeded")
	}
	if fixture.workspace.links[location] != before || fixture.workspace.writeCount() != 0 ||
		len(fixture.store.ownership.Claims()) != 0 || fixture.store.journal != nil {
		t.Fatalf(
			"failed adoption left state: %#v %#v %#v",
			fixture.workspace.links[location], fixture.store.ownership.Claims(), fixture.store.journal,
		)
	}
}

func TestApplyRejectsSameTargetIdentitySubstitutionAfterRefresh(t *testing.T) {
	location := testLocation("one")
	observed := linkState("source/old")
	operation := claimedMutation(domain.OperationRemove, location, observed, "")
	preview := testPreview("release", "digest", nil, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = observed
	fixture.workspace.links[location] = LinkState{
		Exists: true, RawTarget: observed.RawTarget, Parent: observed.Parent,
		Entry: FileIdentity{Device: observed.Entry.Device, Inode: observed.Entry.Inode + 1},
	}
	fixture.store.ownership = registryWith(t, claimFor(operation, observed.RawTarget, "old-release", testDigest("old")))

	_, err := fixture.executor().Apply(preview)
	if err == nil || !strings.Contains(err.Error(), "identity changed after preview") {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.store.ownershipSaveCalls != 0 || fixture.workspace.writeCount() != 0 {
		t.Fatal("identity substitution caused writes")
	}
}

func TestApplyRemovesDanglingClaimWithoutCatalogSource(t *testing.T) {
	location := testLocation("retired")
	before := linkState("source/missing")
	operation := claimedMutation(domain.OperationRemove, location, before, "")
	operation.ComponentID = "retired"
	operation.UnitID = "retired.link"
	operation.Artifact.UnitID = operation.UnitID
	preview := testPreview("release", "digest", nil, operation)
	fixture := newFixture(preview)
	fixture.workspace.links[location] = before
	fixture.store.ownership = registryWith(t, claimFor(operation, before.RawTarget, "old-release", testDigest("old")))

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.links[location].Exists || len(fixture.store.ownership.Claims()) != 0 {
		t.Fatalf("link or claim remains: %#v %#v", fixture.workspace.links[location], fixture.store.ownership.Claims())
	}
}

func TestApplyReinstallsMissingClaimedLink(t *testing.T) {
	location := testLocation("one")
	operation := claimedInstall("one", "source/new")
	operation.Artifact = domain.Artifact{
		Location: location, UnitID: operation.UnitID,
		Ownership: domain.OwnershipManagedMissing, RawTarget: "source/old",
	}
	preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
	fixture := newFixture(preview)
	fixture.store.ownership = registryWith(t, claimFor(
		operation, "source/old", "old-release", testDigest("old"),
	))

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if got := fixture.workspace.links[location]; !got.Exists || got.RawTarget != "source/new" {
		t.Fatalf("reinstalled link = %#v", got)
	}
	claim, exists := fixture.store.ownership.ClaimAt(location)
	if !exists || claim.RawTarget != "source/new" || claim.ReleaseID != "release" {
		t.Fatalf("reinstalled claim = %#v, exists = %t", claim, exists)
	}
}

func TestApplyRelinquishesMissingClaimWithoutFilesystemWrite(t *testing.T) {
	location := testLocation("one")
	operation := domain.Operation{
		ComponentID: "codex", UnitID: "codex.one", Kind: domain.OperationRelinquish,
		Artifact: domain.Artifact{
			Location: location, UnitID: "codex.one",
			Ownership: domain.OwnershipManagedMissing, RawTarget: "source/old",
		},
	}
	preview := testPreview("release", "digest", nil, operation)
	fixture := newFixture(preview)
	fixture.store.ownership = registryWith(t, claimFor(
		operation, "source/old", "old-release", testDigest("old"),
	))

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if len(fixture.store.ownership.Claims()) != 0 || fixture.workspace.writeCount() != 0 {
		t.Fatalf(
			"relinquishment left claim or wrote filesystem: %#v %d",
			fixture.store.ownership.Claims(), fixture.workspace.writeCount(),
		)
	}
}

func TestApplyRelinquishesDriftedClaimWithoutInspectingTargetKind(t *testing.T) {
	location := testLocation("one")
	operation := domain.Operation{
		ComponentID: "codex", UnitID: "codex.one", Kind: domain.OperationRelinquish,
		Artifact: domain.Artifact{
			Location: location, UnitID: "codex.one",
			Ownership:  domain.OwnershipManagedDrifted,
			LinkDevice: 7, LinkInode: 8,
		},
	}
	preview := testPreview("release", "digest", nil, operation)
	fixture := newFixture(preview)
	fixture.workspace.inspectErr = errors.New("target entry is not a symbolic link")
	fixture.store.ownership = registryWith(t, claimFor(
		operation, "source/old", "old-release", testDigest("old"),
	))

	if _, err := fixture.executor().Apply(preview); err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if fixture.workspace.inspectCalls != 0 || len(fixture.store.ownership.Claims()) != 0 {
		t.Fatalf(
			"relinquishment inspected target or left claim: %d %#v",
			fixture.workspace.inspectCalls, fixture.store.ownership.Claims(),
		)
	}
}

func TestApplyRecoversAtEveryOwnershipPersistenceBoundary(t *testing.T) {
	tests := []struct {
		name string
		fail func(*fakeStore)
	}{
		{name: "registry before write", fail: func(store *fakeStore) { store.ownershipFailAt = 1 }},
		{name: "registry outcome unknown", fail: func(store *fakeStore) { store.ownershipFailAfterAt = 1 }},
		{name: "claim journal phase", fail: func(store *fakeStore) { store.saveFailAt = 5 }},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			operation := claimedInstall("one", "source/one")
			preview := testPreview("release", "digest", []domain.ComponentID{"codex"}, operation)
			fixture := newFixture(preview)
			test.fail(fixture.store)

			if _, err := fixture.executor().Apply(preview); err == nil {
				t.Fatal("Apply() unexpectedly succeeded")
			}
			if fixture.workspace.links[operation.Artifact.Location].Exists ||
				len(fixture.store.ownership.Claims()) != 0 || fixture.store.journal != nil {
				t.Fatalf(
					"recovery left link, claim, or journal: %#v %#v %#v",
					fixture.workspace.links[operation.Artifact.Location],
					fixture.store.ownership.Claims(), fixture.store.journal,
				)
			}
		})
	}
}

func claimedInstall(path, source domain.ArtifactPath) domain.Operation {
	operation := install(path, source)
	operation.UnitID = "codex." + string(path)
	return operation
}

func claimedMutation(kind domain.OperationKind, location domain.Location, before LinkState, source domain.ArtifactPath) domain.Operation {
	return domain.Operation{
		ComponentID: "codex", UnitID: "codex.one", Kind: kind,
		Artifact: domain.Artifact{
			Location: location, UnitID: "codex.one", Ownership: domain.OwnershipManagedPrevious,
			RawTarget:  before.RawTarget,
			LinkDevice: before.Entry.Device, LinkInode: before.Entry.Inode,
		},
		SourcePath: source,
	}
}

func claimFor(operation domain.Operation, raw, release, digest string) linkownership.Claim {
	return linkownership.Claim{
		UnitID: operation.UnitID, ComponentID: operation.ComponentID,
		Target: operation.Artifact.Location, RawTarget: raw,
		ReleaseID: release, IndexSHA256: digest,
	}
}

func registryWith(t *testing.T, claims ...linkownership.Claim) linkownership.Registry {
	t.Helper()
	registry, err := linkownership.New(claims)
	if err != nil {
		t.Fatalf("new ownership registry: %v", err)
	}
	return registry
}
