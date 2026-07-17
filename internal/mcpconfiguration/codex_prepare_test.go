package mcpconfiguration_test

import (
	"crypto/sha256"
	"fmt"
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const codexManagedFormat = "codex-toml-block-v1"

func TestPrepareCodexAddPreservesUnrelatedTOMLBytes(t *testing.T) {
	original := []byte("model = \"gpt\"\n# keep this comment\n")
	host := codexPreparedHost(original, nil)
	inspection := inspectCodexPrepared(t, host)

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex},
		codexSelection(),
	)
	if err != nil {
		t.Fatalf("Prepare() error = %v", err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	wantConfig := append(
		append([]byte(nil), original...),
		[]byte("\n"+codexManagedBlock("https://mcp.context7.com/mcp", "suffix-newline", "\n"))...,
	)
	assertCodexMutation(t, mutations[0], codexLocation("config.toml"), original, 0o644, 101, wantConfig)
	if !strings.Contains(string(mutations[1].After), `"format": "`+codexManagedFormat+`"`) ||
		!strings.Contains(string(mutations[1].After), `"entry": {`) {
		t.Fatalf("registry after-image lacks marker provenance:\n%s", mutations[1].After)
	}
}

func TestPrepareCodexAddToMissingFilesUsesPrivateMode(t *testing.T) {
	host := codexPreparedHost(nil, nil)
	inspection := inspectCodexPrepared(t, host)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex},
		codexSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 2 {
		t.Fatalf("mutations = %#v", mutations)
	}
	for _, mutation := range mutations {
		if mutation.Before.Exists || mutation.Mode != 0o600 {
			t.Fatalf("missing-file mutation = %#v", mutation)
		}
	}
	if got := string(mutations[0].After); got != codexManagedBlock(
		"https://mcp.context7.com/mcp", "empty", "\n",
	) {
		t.Fatalf("config after-image:\n%s", got)
	}
}

func TestPrepareCodexUpdateAndRemoveOwnOnlyTheExactSuffix(t *testing.T) {
	original := []byte("model = \"gpt\"\r\n")
	oldURL := "https://old.example/mcp"
	oldBlock := codexManagedBlock(oldURL, "suffix-newline", "\r\n")
	config := append(append([]byte(nil), original...), []byte("\r\n"+oldBlock)...)
	registry := []byte(codexManagedRegistry(oldURL))

	t.Run("update", func(t *testing.T) {
		inspection := inspectCodexPrepared(t, codexPreparedHost(config, registry))
		prepared, err := inspection.Prepare(
			[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
		)
		if err != nil {
			t.Fatal(err)
		}
		mutations := prepared.Transitions()[0].Mutations
		want := append(
			append([]byte(nil), original...),
			[]byte("\r\n"+codexManagedBlock(
				"https://mcp.context7.com/mcp", "suffix-newline", "\r\n",
			))...,
		)
		if !reflect.DeepEqual(mutations[0].After, want) {
			t.Fatalf("updated config:\n%s", mutations[0].After)
		}
	})

	t.Run("remove", func(t *testing.T) {
		inspection := inspectCodexPrepared(t, codexPreparedHost(config, registry))
		prepared, err := inspection.Prepare(
			[]domain.ComponentID{domain.ComponentCodex}, nil,
		)
		if err != nil {
			t.Fatal(err)
		}
		mutations := prepared.Transitions()[0].Mutations
		if !reflect.DeepEqual(mutations[0].After, original) {
			t.Fatalf("remove did not restore original bytes: %q", mutations[0].After)
		}
		if strings.Contains(string(mutations[1].After), `"context7"`) {
			t.Fatalf("registry retained removed ownership:\n%s", mutations[1].After)
		}
	})
}

func TestPrepareCodexRemoveAllowsAnEmptyTOMLAfterImage(t *testing.T) {
	config := []byte(codexManagedBlock(
		"https://mcp.context7.com/mcp", "empty", "\n",
	))
	inspection := inspectCodexPrepared(
		t,
		codexPreparedHost(config, []byte(codexManagedRegistry("https://mcp.context7.com/mcp"))),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex}, nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	if got := prepared.Transitions()[0].Mutations[0].After; len(got) != 0 {
		t.Fatalf("removed block left bytes %q", got)
	}
}

func TestPrepareCodexRelinquishMutatesOnlyTheRegistry(t *testing.T) {
	url := "https://mcp.context7.com/mcp"
	config := []byte(codexManagedBlock(url, "empty", "\n") + "headers = { user = \"kept\" }\n")
	inspection := inspectCodexPrepared(
		t,
		codexPreparedHost(config, []byte(codexManagedRegistry(url))),
	)
	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	mutations := prepared.Transitions()[0].Mutations
	if len(mutations) != 1 || mutations[0].Target != codexLocation("mainframe/mcp-ownership.json") ||
		!strings.Contains(string(mutations[0].After), `"context7": null`) {
		t.Fatalf("relinquish mutations = %#v", mutations)
	}
}

func TestPrepareCodexRejectsUnprovenOrEditedManagedBlocks(t *testing.T) {
	oldURL := "https://old.example/mcp"
	validBlock := codexManagedBlock(oldURL, "empty", "\n")
	tests := map[string]struct {
		config   string
		registry string
	}{
		"legacy registry": {
			config: validBlock, registry: codexOwned(`{"url":"` + oldURL + `"}`),
		},
		"edited marker": {
			config:   strings.Replace(validBlock, " end\n", " edited end\n", 1),
			registry: codexManagedRegistry(oldURL),
		},
		"block is not the suffix": {
			config:   validBlock + "[other]\nvalue = true\n",
			registry: codexManagedRegistry(oldURL),
		},
		"marker text inside multiline string": {
			config:   "note = '''\n" + validBlock + "'''\n" + codexTOML(oldURL),
			registry: codexOwned(`{"url":"` + oldURL + `"}`),
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			inspection := inspectCodexPrepared(
				t,
				codexPreparedHost([]byte(test.config), []byte(test.registry)),
			)
			prepared, err := inspection.Prepare(
				[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
			)
			if err == nil || len(prepared.Transitions()) != 0 {
				t.Fatalf("Prepare() = %#v, %v", prepared, err)
			}
		})
	}
}

func TestPrepareCodexUsesImmutableDeduplicatedSnapshots(t *testing.T) {
	config := []byte("model = \"gpt\"\n")
	host := codexPreparedHost(config, nil)
	inspection := inspectCodexPrepared(t, host)
	if host.reads != 2 {
		t.Fatalf("inspection reads = %d, want 2", host.reads)
	}
	host.entries[codexLocation("config.toml")].Content[0] = 'x'
	reads := host.reads

	first, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	exposed := first.Transitions()
	exposed[0].Mutations[0].After[0] = 'x'
	second, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if host.reads != reads || reflect.DeepEqual(exposed, second.Transitions()) ||
		second.Transitions()[0].Mutations[0].After[0] != 'm' {
		t.Fatalf("preparation was not immutable: reads=%d transitions=%#v", host.reads, second.Transitions())
	}
}

func TestPrepareCodexRejectsUnsafeModesAndPhysicalAliases(t *testing.T) {
	config := []byte("model = \"gpt\"\n")
	registry := []byte(`{"version":1,"servers":{}}`)

	t.Run("read-only remains read-only", func(t *testing.T) {
		host := codexPreparedHost(config, registry)
		entry := host.entries[codexLocation("config.toml")]
		entry.Mode = 0o400
		host.entries[codexLocation("config.toml")] = entry
		inspection := inspectCodexPrepared(t, host)
		prepared, err := inspection.Prepare(
			[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
		)
		if err != nil {
			t.Fatal(err)
		}
		if got := prepared.Transitions()[0].Mutations[0].Mode; got != 0o400 {
			t.Fatalf("prepared mode = %#o, want 0400", got)
		}
	})

	t.Run("unreadable", func(t *testing.T) {
		host := codexPreparedHost(config, registry)
		entry := host.entries[codexLocation("config.toml")]
		entry.Mode = 0o200
		host.entries[codexLocation("config.toml")] = entry
		inspection := inspectCodexPrepared(t, host)
		if _, err := inspection.Prepare(
			[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
		); err == nil {
			t.Fatal("Prepare() accepted unreadable target")
		}
	})

	t.Run("physical alias", func(t *testing.T) {
		host := codexPreparedHost(config, registry)
		entry := host.entries[codexLocation("mainframe/mcp-ownership.json")]
		entry.Inode = 101
		host.entries[codexLocation("mainframe/mcp-ownership.json")] = entry
		inspection := inspectCodexPrepared(t, host)
		if _, err := inspection.Prepare(
			[]domain.ComponentID{domain.ComponentCodex}, codexSelection(),
		); err == nil {
			t.Fatal("Prepare() accepted physical aliases")
		}
	})
}

func TestCodexSingleBlockFormatRejectsMultipleReleaseProjections(t *testing.T) {
	second := codexProjection()
	second.ID = "codex.mcp.second"
	_, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{codexProjection(), second},
		catalog(t),
		&fakeHost{},
	)
	if err == nil || !strings.Contains(err.Error(), "one Codex MCP projection") {
		t.Fatalf("Inspect() error = %v", err)
	}
}

func inspectCodexPrepared(t *testing.T, host *fakeHost) mcpconfiguration.Inspection {
	t.Helper()
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{codexProjection()}, catalog(t), host,
	)
	if err != nil {
		t.Fatal(err)
	}
	return inspection
}

func codexSelection() []mcpcatalog.Selection {
	return []mcpcatalog.Selection{{
		ServerID: "context7", ProfileID: "remote-keyless",
		Adapters: []domain.ComponentID{domain.ComponentCodex},
	}}
}

func codexPreparedHost(config, registry []byte) *fakeHost {
	entries := make(map[domain.Location]hostfs.Entry)
	if config != nil {
		entries[codexLocation("config.toml")] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), config...),
			Mode: 0o644, Device: 7, Inode: 101,
		}
	}
	if registry != nil {
		entries[codexLocation("mainframe/mcp-ownership.json")] = hostfs.Entry{
			Kind: hostfs.EntryRegular, Content: append([]byte(nil), registry...),
			Mode: 0o600, Device: 7, Inode: 102,
		}
	}
	return &fakeHost{entries: entries}
}

func codexManagedBlock(endpoint, layout, newline string) string {
	return strings.Join([]string{
		"# MAINFRAME managed MCP v1 context7 " + layout + " begin",
		`[mcp_servers."context7"]`,
		`url = "` + endpoint + `"`,
		"# MAINFRAME managed MCP v1 context7 end",
		"",
	}, newline)
}

func codexManagedRegistry(endpoint string) string {
	return `{"version":1,"servers":{"context7":{"format":"` + codexManagedFormat +
		`","entry":{"url":"` + endpoint + `"}}}}`
}

func assertCodexMutation(
	t *testing.T,
	mutation configuration.FileMutation,
	target domain.Location,
	before []byte,
	mode uint32,
	inode uint64,
	after []byte,
) {
	t.Helper()
	digest := sha256.Sum256(before)
	if mutation.Target != target || !mutation.Before.Exists ||
		mutation.Before.SHA256 != fmt.Sprintf("%x", digest) ||
		mutation.Before.Mode != mode || mutation.Before.Device != 7 ||
		mutation.Before.Inode != inode || mutation.Mode != mode&0o600 ||
		!reflect.DeepEqual(mutation.After, after) {
		t.Fatalf("mutation = %#v", mutation)
	}
}
