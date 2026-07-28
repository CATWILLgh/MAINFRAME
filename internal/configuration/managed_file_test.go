package configuration_test

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io/fs"
	"reflect"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestManagedSeedLifecyclePlansDeterministically(t *testing.T) {
	desired := []byte("managed\n")
	desiredDigest := fmt.Sprintf("%x", sha256.Sum256(desired))
	tests := map[string]struct {
		target   *hostfs.Entry
		registry any
		selected bool
		want     []configuration.ChangeKind
	}{
		"missing selected creates claim": {
			selected: true,
			want:     []configuration.ChangeKind{configuration.ChangeAdd},
		},
		"unowned existing is preserved": {
			target:   &hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			selected: true,
		},
		"matching managed selected is fixed point": {
			target:   &hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			registry: managedClaims(managedClaim(desiredDigest)),
			selected: true,
		},
		"drifted managed relinquishes": {
			target:   &hostfs.Entry{Kind: hostfs.EntryRegular, Content: []byte("user\n"), Mode: 0o600},
			registry: managedClaims(managedClaim(desiredDigest)),
			selected: true,
			want:     []configuration.ChangeKind{configuration.ChangeRelinquish},
		},
		"claimed missing selected recreates": {
			registry: managedClaims(managedClaim(desiredDigest)),
			selected: true,
			want:     []configuration.ChangeKind{configuration.ChangeAdd},
		},
		"claimed missing deselected relinquishes": {
			registry: managedClaims(managedClaim(desiredDigest)),
			want:     []configuration.ChangeKind{configuration.ChangeRelinquish},
		},
		"matching managed deselected removes": {
			target:   &hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			registry: managedClaims(managedClaim(desiredDigest)),
			want:     []configuration.ChangeKind{configuration.ChangeRemove},
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			host := newManagedFileHost(test.target, test.registry)
			inspection, err := configuration.Inspect(
				[]releasecontract.Resource{managedSeedResource(desired)},
				host,
			)
			if err != nil {
				t.Fatalf("Inspect(): %v", err)
			}
			var selected []domain.ComponentID
			if test.selected {
				selected = []domain.ComponentID{"credential-tools"}
			}
			plan, err := inspection.Plan(selected)
			if err != nil {
				t.Fatalf("Plan(): %v", err)
			}
			var got []configuration.ChangeKind
			for _, change := range plan.Changes {
				got = append(got, change.Kind)
			}
			if !reflect.DeepEqual(got, test.want) || len(plan.Issues) != 0 {
				t.Fatalf("plan = %#v, want changes %v", plan, test.want)
			}
			if host.digestCalls != 1 || host.contentCalls[managedTarget()] != 0 {
				t.Fatalf("inspection calls = digest %d, content %#v", host.digestCalls, host.contentCalls)
			}
		})
	}
}

func TestManagedSeedPreparationPublishesTargetAndRegistryTogether(t *testing.T) {
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{managedSeedResource([]byte("managed\n"))},
		newManagedFileHost(nil, nil),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Prepare(): %v", err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || transitions[0].PreparationOnly ||
		len(transitions[0].Mutations) != 2 {
		t.Fatalf("transitions = %#v", transitions)
	}
	if transitions[0].Mutations[0].Target != managedRegistry() ||
		transitions[0].Mutations[1].Target != managedTarget() {
		t.Fatalf("mutation order = %#v", transitions[0].Mutations)
	}
	var registry map[string]any
	if err := json.Unmarshal(transitions[0].Mutations[0].After.Content, &registry); err != nil {
		t.Fatal(err)
	}
	claims, ok := registry["claims"].([]any)
	if !ok || len(claims) != 1 {
		t.Fatalf("registry = %#v", registry)
	}
}

func TestManagedSeedFinalRemovalPreservesEmptyClaimsArray(t *testing.T) {
	desired := []byte("managed\n")
	digest := fmt.Sprintf("%x", sha256.Sum256(desired))
	target := &hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{managedSeedResource(desired)},
		newManagedFileHost(target, managedClaims(managedClaim(digest))),
	)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := inspection.Prepare(nil)
	if err != nil {
		t.Fatalf("Prepare(): %v", err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if mutations[1].Before.SHA256 != digest {
		t.Fatalf(
			"target before digest = %q, want %q",
			mutations[1].Before.SHA256,
			digest,
		)
	}
	if mutations[0].Target != managedRegistry() ||
		string(mutations[0].After.Content) != "{\n  \"schema_version\": 1,\n  \"claims\": []\n}\n" ||
		mutations[1].After.Exists {
		t.Fatalf("mutations = %#v", mutations)
	}

	reloadedHost := newManagedFileHost(nil, nil)
	reloadedHost.entries[managedRegistry()] = hostfs.Entry{
		Kind: hostfs.EntryRegular,
		Content: append(
			[]byte(nil),
			mutations[0].After.Content...,
		),
		Mode: 0o600, Device: 7, Inode: 31, BirthSeconds: 32,
	}
	reloaded, err := configuration.Inspect(
		[]releasecontract.Resource{managedSeedResource(desired)},
		reloadedHost,
	)
	if err != nil {
		t.Fatalf("reload after removal: %v", err)
	}
	reinstall, err := reloaded.Prepare(
		[]domain.ComponentID{"credential-tools"},
	)
	if err != nil {
		t.Fatalf("prepare reinstall: %v", err)
	}
	reinstallMutations := reinstall.Transitions()[0].Mutations
	if len(reinstallMutations) != 2 ||
		!reinstallMutations[1].After.Exists ||
		string(reinstallMutations[1].After.Content) != string(desired) {
		t.Fatalf("reinstall mutations = %#v", reinstallMutations)
	}
}

func TestManagedSeedUnsafeStateBlocksWithoutChanges(t *testing.T) {
	desired := []byte("managed\n")
	digest := fmt.Sprintf("%x", sha256.Sum256(desired))
	symlinkRegistry := newManagedFileHost(
		&hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
		nil,
	)
	symlinkRegistry.entries[managedRegistry()] = hostfs.Entry{
		Kind: hostfs.EntrySymlink,
	}
	tests := map[string]*managedFileHost{
		"symlink target": newManagedFileHost(
			&hostfs.Entry{Kind: hostfs.EntrySymlink},
			managedClaims(managedClaim(digest)),
		),
		"malformed registry": newManagedFileHost(
			&hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			map[string]any{"schema_version": 2, "claims": []any{}},
		),
		"symlink registry": symlinkRegistry,
		"mismatched claim target": newManagedFileHost(
			&hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			managedClaims(map[string]any{
				"resource_id":  "credential-tools.secrets-store",
				"component_id": "credential-tools",
				"target": map[string]any{
					"root": "credentials-config", "path": "foreign.env",
				},
				"sha256": digest, "mode": float64(384),
			}),
		),
		"duplicate claim target": newManagedFileHost(
			&hostfs.Entry{Kind: hostfs.EntryRegular, Content: desired, Mode: 0o600},
			managedClaims(
				managedClaim(digest),
				map[string]any{
					"resource_id":  "credential-tools.zzz",
					"component_id": "credential-tools",
					"target": map[string]any{
						"root": "credentials-config", "path": "secrets.env",
					},
					"sha256": digest, "mode": float64(384),
				},
			),
		),
	}
	for name, host := range tests {
		t.Run(name, func(t *testing.T) {
			inspection, err := configuration.Inspect(
				[]releasecontract.Resource{managedSeedResource(desired)},
				host,
			)
			if err != nil {
				t.Fatalf("Inspect(): %v", err)
			}
			plan, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
			if err != nil {
				t.Fatalf("Plan(): %v", err)
			}
			if len(plan.Issues) != 1 || len(plan.Changes) != 0 {
				t.Fatalf("plan = %#v", plan)
			}
		})
	}
}

func TestManagedSeedTreatsWrappedNotExistAsMissing(t *testing.T) {
	host := newManagedFileHost(nil, nil)
	host.failures = map[domain.Location]error{
		managedTarget():   fmt.Errorf("wrapped target: %w", fs.ErrNotExist),
		managedRegistry(): fmt.Errorf("wrapped registry: %w", fs.ErrNotExist),
	}
	inspection, err := configuration.Inspect(
		[]releasecontract.Resource{managedSeedResource([]byte("managed\n"))},
		host,
	)
	if err != nil {
		t.Fatalf("Inspect(): %v", err)
	}
	if got := inspection.Observations(); len(got) != 1 ||
		got[0].Status != configuration.NeedsChange {
		t.Fatalf("observations = %#v", got)
	}
	plan, err := inspection.Plan([]domain.ComponentID{"credential-tools"})
	if err != nil {
		t.Fatalf("Plan(): %v", err)
	}
	if len(plan.Changes) != 1 ||
		plan.Changes[0].Kind != configuration.ChangeAdd {
		t.Fatalf("changes = %#v", plan.Changes)
	}
}

func managedSeedResource(content []byte) releasecontract.Resource {
	return releasecontract.Resource{
		ID: "credential-tools.secrets-store", ComponentID: "credential-tools",
		Strategy:      releasecontract.StrategySeedIfAbsent,
		SourcePath:    "common/credential-tools/secrets.env",
		SourceContent: append([]byte(nil), content...),
		Target:        managedTarget(), Observation: releasecontract.SupportSupported,
		Apply: releasecontract.SupportSupported,
		FileOwnership: &releasecontract.FileOwnership{
			RegistryTarget: managedRegistry(), RegistrySchemaVersion: 1,
		},
	}
}

func managedTarget() domain.Location {
	return domain.Location{Root: domain.RootCredentialsConfig, Path: "secrets.env"}
}

func managedRegistry() domain.Location {
	return domain.Location{
		Root: domain.RootCredentialsConfig,
		Path: "mainframe/file-ownership.json",
	}
}

func managedClaim(digest string) map[string]any {
	return map[string]any{
		"resource_id":  "credential-tools.secrets-store",
		"component_id": "credential-tools",
		"target": map[string]any{
			"root": "credentials-config", "path": "secrets.env",
		},
		"sha256": digest,
		"mode":   float64(384),
	}
}

func managedClaims(claims ...map[string]any) map[string]any {
	return map[string]any{"schema_version": 1, "claims": claims}
}

type managedFileHost struct {
	entries      map[domain.Location]hostfs.Entry
	failures     map[domain.Location]error
	digestCalls  int
	contentCalls map[domain.Location]int
}

func newManagedFileHost(target *hostfs.Entry, registry any) *managedFileHost {
	host := &managedFileHost{
		entries:      make(map[domain.Location]hostfs.Entry),
		contentCalls: make(map[domain.Location]int),
	}
	if target != nil {
		entry := *target
		entry.Device = 7
		entry.Inode = 11
		entry.BirthSeconds = 12
		host.entries[managedTarget()] = entry
	}
	if registry != nil {
		raw, _ := json.Marshal(registry)
		host.entries[managedRegistry()] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: raw, Mode: 0o600,
			Device: 7, Inode: 21, BirthSeconds: 22,
		}
	}
	return host
}

func (host *managedFileHost) Inspect(
	location domain.Location,
	includeContent bool,
) (hostfs.Entry, error) {
	host.contentCalls[location]++
	entry, exists := host.entries[location]
	if err := host.failures[location]; err != nil {
		return hostfs.Entry{}, err
	}
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	if !includeContent {
		entry.Content = nil
	}
	return entry, nil
}

func (host *managedFileHost) InspectDigest(
	location domain.Location,
) (hostfs.Entry, error) {
	host.digestCalls++
	if err := host.failures[location]; err != nil {
		return hostfs.Entry{}, err
	}
	entry, exists := host.entries[location]
	if !exists {
		return hostfs.Entry{}, fs.ErrNotExist
	}
	if entry.Kind == hostfs.EntryRegular {
		entry.SHA256 = fmt.Sprintf("%x", sha256.Sum256(entry.Content))
		entry.Content = nil
	}
	return entry, nil
}
