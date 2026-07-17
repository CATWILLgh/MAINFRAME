package mcpconfiguration_test

import (
	"reflect"
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPrepareClaudeComposesMixedExistingIntents(t *testing.T) {
	oldContext := `{"type":"http","url":"https://old.example/mcp"}`
	docs := `{"type":"http","url":"https://docs.example/mcp"}`
	config := []byte(
		`{"mcpServers":{"context7":` + oldContext + `,"docs":` + docs + `},"keep":true}`,
	)
	registry := []byte(
		`{"version":1,"servers":{"context7":` + oldContext + `,"docs":` + docs + `}}`,
	)
	second := claudeProjection()
	second.ID = "claude-code.mcp.docs"
	second.ServerID = "docs"
	second.EntryKey = "docs"
	second.DesiredEntry = docs
	inspection, err := mcpconfiguration.Inspect(
		[]releasecontract.MCPProjection{claudeProjection(), second},
		twoServerCatalog(t),
		claudePreparedHost(config, registry),
	)
	if err != nil {
		t.Fatal(err)
	}

	prepared, err := inspection.Prepare(
		[]domain.ComponentID{domain.ComponentClaudeCode}, claudeSelection(),
	)
	if err != nil {
		t.Fatal(err)
	}
	transitions := prepared.Transitions()
	if len(transitions) != 1 || len(transitions[0].Mutations) != 2 ||
		!reflect.DeepEqual(
			transitions[0].ResourceIDs,
			[]string{"claude-code.mcp.context7", "claude-code.mcp.docs"},
		) {
		t.Fatalf("mixed preparation = %#v", transitions)
	}
	configAfter := claudeMutationAt(
		t, transitions[0], claudeLocation(".claude.json"),
	).After
	registryAfter := claudeMutationAt(
		t,
		transitions[0],
		second.RegistryTarget,
	).After
	for _, after := range [][]byte{configAfter, registryAfter} {
		if strings.Contains(string(after), `"docs"`) ||
			!strings.Contains(string(after), `"https://mcp.context7.com/mcp"`) {
			t.Fatalf("mixed after-image =\n%s", after)
		}
	}
	if !strings.Contains(string(configAfter), `"keep": true`) {
		t.Fatalf("unrelated preference was lost:\n%s", configAfter)
	}
}
