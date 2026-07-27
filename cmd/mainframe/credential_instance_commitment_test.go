package main

import (
	"io/fs"
	"regexp"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/credentialcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
)

func TestCredentialReviewCommitmentIsStableAndBindsItsScope(t *testing.T) {
	useCredentialsEnvironment(t)
	definitions := loadProtocolDefinitions(t)
	desired, err := credentialcatalog.BuildInstances(
		[]credentialcatalog.Instance{testProtocolInstance()},
		definitions,
	)
	if err != nil {
		t.Fatalf("build instances: %v", err)
	}
	preview := credentialCommitmentPreview(t, definitions, desired, hostfs.Entry{})
	scope := credentialCommitmentScope{
		CredentialTarget: "/home/user/.config/credentials/mainframe/instances.json",
		TransactionState: "/home/user/.local/state/mainframe",
		ReleaseRoot:      "/opt/mainframe/release",
	}
	digest, err := credentialReviewCommitment(preview, desired, scope)
	if err != nil {
		t.Fatalf("commitment: %v", err)
	}
	if !regexp.MustCompile(`^sha256:[0-9a-f]{64}$`).MatchString(digest) {
		t.Fatalf("digest = %q", digest)
	}
	const golden = "sha256:c0b994db2eb83c1b29b466c4343c96e097c9ea03d4d55f3a73d83018442c73ee"
	if digest != golden {
		t.Fatalf("digest = %q, want %q", digest, golden)
	}
	if again, err := credentialReviewCommitment(
		preview,
		desired,
		scope,
	); err != nil || again != digest {
		t.Fatalf("repeat commitment = %q, %v", again, err)
	}
	assertCredentialCommitmentChanges(
		t,
		digest,
		preview,
		desired,
		scope,
	)
}

func assertCredentialCommitmentChanges(
	t *testing.T,
	digest string,
	preview executor.Preview,
	desired credentialcatalog.Instances,
	scope credentialCommitmentScope,
) {
	t.Helper()
	changedRelease := preview
	changedRelease.Release.ID = "other-release"
	if changed, _ := credentialReviewCommitment(
		changedRelease,
		desired,
		scope,
	); changed == digest {
		t.Fatal("release drift did not change commitment")
	}
	changedScope := scope
	changedScope.CredentialTarget = "/other/credentials/mainframe/instances.json"
	if changed, _ := credentialReviewCommitment(
		preview,
		desired,
		changedScope,
	); changed == digest {
		t.Fatal("physical target drift did not change commitment")
	}
	present := hostfs.Entry{
		Kind: hostfs.EntryRegular, Mode: 0o600,
		Content: []byte(`{"schema_version":1,"kind":"mainframe-credential-instances","instances":[]}`),
		Device:  7, Inode: 9, BirthSeconds: 11, BirthNanoseconds: 13,
	}
	changedBefore := credentialCommitmentPreview(
		t,
		loadProtocolDefinitions(t),
		desired,
		present,
	)
	if changed, _ := credentialReviewCommitment(
		changedBefore,
		desired,
		scope,
	); changed == digest {
		t.Fatal("before-image drift did not change commitment")
	}
}

type protocolInstanceHost struct {
	entry hostfs.Entry
}

func (host protocolInstanceHost) Inspect(
	domain.Location,
	bool,
) (hostfs.Entry, error) {
	if host.entry.Kind == "" {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	return host.entry, nil
}

func credentialCommitmentPreview(
	t *testing.T,
	definitions credentialcatalog.Definitions,
	desired credentialcatalog.Instances,
	entry hostfs.Entry,
) executor.Preview {
	t.Helper()
	snapshot, err := credentialcatalog.ObserveInstances(
		protocolInstanceHost{entry: entry},
		definitions,
	)
	if err != nil {
		t.Fatalf("observe instances: %v", err)
	}
	prepared, err := snapshot.Prepare(desired)
	if err != nil {
		t.Fatalf("prepare instances: %v", err)
	}
	return executor.Preview{
		Release:       executor.ReleaseIdentity{ID: "release", IndexSHA256: "index"},
		Configuration: prepared,
	}
}

func loadProtocolDefinitions(t *testing.T) credentialcatalog.Definitions {
	t.Helper()
	definitions, _, err := loadCredentialCatalog()
	if err != nil {
		t.Fatalf("load catalog: %v", err)
	}
	return definitions
}

func testProtocolInstance() credentialcatalog.Instance {
	return credentialcatalog.Instance{
		ID: "context7-home", ServiceID: "context7",
		Name: "Home", Purpose: "Personal research",
		Credentials: []credentialcatalog.CredentialBinding{{
			RoleID: "api-key",
			Secret: credentialcatalog.SecretReference{
				Backend: "secret-env", Name: "CONTEXT7_SHARED_KEY",
			},
		}},
	}
}
