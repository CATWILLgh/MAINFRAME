package mcpcatalog

import (
	"os"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func TestSourceCatalogMatchesGoContract(t *testing.T) {
	payload, err := os.ReadFile("catalog.json")
	if err != nil {
		t.Fatalf("read source catalog: %v", err)
	}
	if _, err := Parse(payload); err != nil {
		t.Fatalf("parse source catalog: %v", err)
	}
}

func TestParseAcceptsCompleteContext7Profiles(t *testing.T) {
	catalog, err := Parse(validCatalogJSON())
	if err != nil {
		t.Fatalf("parse catalog: %v", err)
	}
	server, exists := catalog.Server("context7")
	if !exists {
		t.Fatal("Context7 is absent")
	}
	if server.Repository.Owner != "upstash" || server.License != "MIT" {
		t.Fatalf("server metadata = %#v", server)
	}
	keyless, exists := server.Profile("remote-keyless")
	if !exists || keyless.Authentication.Kind != AuthenticationNone {
		t.Fatalf("keyless profile = %#v", keyless)
	}
	if support, _ := keyless.Support(domain.ComponentAntigravity2); support != Supported {
		t.Fatalf("Antigravity keyless support = %q", support)
	}
	keyed, exists := server.Profile("remote-api-key")
	if !exists || keyed.Authentication.EnvironmentVariable != "CONTEXT7_API_KEY" {
		t.Fatalf("keyed profile = %#v", keyed)
	}
	if support, reason := keyed.Support(domain.ComponentAntigravity2); support != Supported || reason != "" {
		t.Fatalf("Antigravity keyed support = %q, %q", support, reason)
	}
}

func TestCatalogAccessorsDoNotExposeMutableSlices(t *testing.T) {
	catalog, err := Parse(validCatalogJSON())
	if err != nil {
		t.Fatalf("parse catalog: %v", err)
	}
	servers := catalog.Servers()
	servers[0].Profiles[0].Compatibility[0].Reason = "mutated"
	server, _ := catalog.Server("context7")
	profile, _ := server.Profile("remote-api-key")
	if profile.Compatibility[0].Reason == "mutated" {
		t.Fatal("catalog accessor exposed mutable compatibility state")
	}
}

func TestParseRejectsUnknownDuplicateAndIncoherentFields(t *testing.T) {
	tests := map[string]string{
		"unknown field": strings.Replace(
			string(validCatalogJSON()), `"kind": "mainframe-mcp-catalog"`,
			`"kind": "mainframe-mcp-catalog", "unknown": true`, 1,
		),
		"duplicate field": strings.Replace(
			string(validCatalogJSON()), `"schema_version": 1`,
			`"schema_version": 1, "schema_version": 1`, 1,
		),
		"keyless variable": strings.Replace(
			string(validCatalogJSON()),
			`"kind": "none", "placement": "none", "environment_variable": ""`,
			`"kind": "none", "placement": "none", "environment_variable": "SHOULD_NOT_EXIST"`, 1,
		),
		"insecure endpoint": strings.Replace(
			string(validCatalogJSON()), "https://mcp.context7.com/mcp",
			"http://mcp.context7.com/mcp", 1,
		),
		"mismatched repository": strings.Replace(
			string(validCatalogJSON()), "https://github.com/upstash/context7",
			"https://github.com/upstash/another-project", 1,
		),
	}
	for name, payload := range tests {
		t.Run(name, func(t *testing.T) {
			if _, err := Parse([]byte(payload)); err == nil {
				t.Fatal("invalid catalog was accepted")
			}
		})
	}
}

func validCatalogJSON() []byte {
	return []byte(`{
  "schema_version": 1,
  "kind": "mainframe-mcp-catalog",
  "servers": [{
    "id": "context7",
    "name": "Context7",
    "summary": "Current library documentation for coding agents.",
    "publisher": "Upstash",
    "homepage_url": "https://context7.com",
    "documentation_url": "https://context7.com/docs/resources/all-clients",
    "repository": {"owner": "upstash", "name": "context7", "url": "https://github.com/upstash/context7"},
    "license": "MIT",
    "profiles": [{
      "id": "remote-api-key",
      "name": "Remote with API key",
      "transport": "streamable-http",
      "endpoint": "https://mcp.context7.com/mcp",
      "authentication": {"kind": "api-key", "placement": "header", "environment_variable": "CONTEXT7_API_KEY"},
      "compatibility": [
        {"adapter": "antigravity-2", "status": "supported", "reason": ""},
        {"adapter": "claude-code", "status": "supported", "reason": ""},
        {"adapter": "codex", "status": "supported", "reason": ""},
        {"adapter": "opencode", "status": "supported", "reason": ""}
      ],
      "evidence": {"url": "https://github.com/upstash/context7#installation", "verified_on": "2026-07-17"}
    }, {
      "id": "remote-keyless",
      "name": "Remote without API key",
      "transport": "streamable-http",
      "endpoint": "https://mcp.context7.com/mcp",
      "authentication": {"kind": "none", "placement": "none", "environment_variable": ""},
      "compatibility": [
        {"adapter": "antigravity-2", "status": "supported", "reason": ""},
        {"adapter": "claude-code", "status": "supported", "reason": ""},
        {"adapter": "codex", "status": "supported", "reason": ""},
        {"adapter": "opencode", "status": "supported", "reason": ""}
      ],
      "evidence": {"url": "https://github.com/upstash/context7#installation", "verified_on": "2026-07-17"}
    }]
  }]
}`)
}
