package linkownership_test

import (
	"bytes"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
)

const releaseDigest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

func TestRegistryRoundTripIsDeterministicAndOwned(t *testing.T) {
	registry, err := linkownership.New([]linkownership.Claim{
		claim("opencode", "opencode.instructions", domain.RootOpenCodeConfig, "AGENTS.md", "/releases/old/opencode/AGENTS.md"),
		claim("claude-code", "claude-code.plugin", domain.RootClaudeConfig, "plugins/mainframe", "/releases/old/claude/plugin"),
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	encoded, err := linkownership.Encode(registry)
	if err != nil {
		t.Fatalf("Encode() error = %v", err)
	}
	decoded, err := linkownership.Decode(encoded)
	if err != nil {
		t.Fatalf("Decode() error = %v", err)
	}
	reencoded, err := linkownership.Encode(decoded)
	if err != nil {
		t.Fatalf("Encode(decoded) error = %v", err)
	}
	if !bytes.Equal(encoded, reencoded) {
		t.Fatalf("encoding is not deterministic:\n%s\n%s", encoded, reencoded)
	}
	claims := decoded.Claims()
	if len(claims) != 2 || claims[0].ComponentID != domain.ComponentClaudeCode {
		t.Fatalf("claims = %#v", claims)
	}
	claims[0].RawTarget = "changed"
	if decoded.Claims()[0].RawTarget == "changed" {
		t.Fatal("Claims() exposed registry state")
	}
}

func TestRegistryReplacesAndRemovesClaimsByExactTarget(t *testing.T) {
	old := claim("codex", "codex.instructions", domain.RootCodexConfig, "AGENTS.md", "/releases/old/codex/AGENTS.md")
	registry, err := linkownership.New([]linkownership.Claim{old})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}
	loaded, exists := registry.ClaimAt(old.Target)
	if !exists || loaded != old {
		t.Fatalf("ClaimAt() = %#v, %t", loaded, exists)
	}
	updated := old
	updated.RawTarget = "/releases/new/codex/AGENTS.md"
	updated.ReleaseID = "new-release"
	registry, err = registry.Put(updated)
	if err != nil {
		t.Fatalf("Put() error = %v", err)
	}
	if loaded, _ := registry.ClaimAt(old.Target); loaded != updated {
		t.Fatalf("updated claim = %#v", loaded)
	}
	registry, removed := registry.Remove(old.Target)
	if !removed || len(registry.Claims()) != 0 {
		t.Fatalf("Remove() = %#v, %t", registry.Claims(), removed)
	}
}

func TestRegistryRejectsAmbiguousOrUnsafeClaims(t *testing.T) {
	base := claim("codex", "codex.instructions", domain.RootCodexConfig, "AGENTS.md", "/releases/old/codex/AGENTS.md")
	tests := []struct {
		name   string
		claims []linkownership.Claim
	}{
		{name: "duplicate unit", claims: []linkownership.Claim{base, base}},
		{name: "duplicate target", claims: []linkownership.Claim{base, claim("codex", "codex.other", domain.RootCodexConfig, "AGENTS.md", "/releases/old/codex/other")}},
		{name: "invalid unit", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.UnitID = "Bad ID" })}},
		{name: "invalid component", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.ComponentID = "Bad" })}},
		{name: "invalid target", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.Target.Path = "../escape" })}},
		{name: "empty raw target", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.RawTarget = "" })}},
		{name: "invalid release", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.ReleaseID = "Bad ID" })}},
		{name: "invalid digest", claims: []linkownership.Claim{mutate(base, func(value *linkownership.Claim) { value.IndexSHA256 = "short" })}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := linkownership.New(test.claims); err == nil {
				t.Fatal("New() accepted unsafe claims")
			}
		})
	}
}

func TestDecodeRejectsUnknownFieldsTrailingDataAndOversize(t *testing.T) {
	valid := `{"schema_version":1,"claims":[]}`
	for _, input := range []string{
		`{"schema_version":1,"claims":[],"unknown":true}`,
		valid + `{}`,
		`{"schema_version":2,"claims":[]}`,
		strings.Repeat(" ", linkownership.MaxRegistryBytes+1),
	} {
		if _, err := linkownership.Decode([]byte(input)); err == nil {
			t.Fatalf("Decode() accepted %d-byte invalid registry", len(input))
		}
	}
}

func claim(component, unit string, root domain.RootID, path domain.ArtifactPath, rawTarget string) linkownership.Claim {
	return linkownership.Claim{
		UnitID: unit, ComponentID: domain.ComponentID(component),
		Target: domain.Location{Root: root, Path: path}, RawTarget: rawTarget,
		ReleaseID: "old-release", IndexSHA256: releaseDigest,
	}
}

func mutate(value linkownership.Claim, change func(*linkownership.Claim)) linkownership.Claim {
	change(&value)
	return value
}
