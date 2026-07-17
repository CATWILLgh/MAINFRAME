package tui

import (
	"strings"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
)

func TestMCPConfigurationPlanRendersPrivacySafeMigrationNoticeWithoutIntents(
	t *testing.T,
) {
	output := renderMCPConfigurationPlan(mcpconfiguration.Plan{
		Migrations: []mcpconfiguration.MigrationAssessment{{
			ComponentID:       domain.ComponentAntigravity2,
			State:             mcpconfiguration.MigrationLegacyOnly,
			RequiresMigration: true,
			Reason: "private-server https://private.example/mcp " +
				"Authorization private-token",
		}},
	})

	if !strings.Contains(output, "Legacy Antigravity MCP configuration detected") ||
		!strings.Contains(output, "migration is required before Antigravity MCP changes") {
		t.Fatalf("migration notice is missing:\n%s", output)
	}
	if strings.Contains(output, "No MCP configuration changes") {
		t.Fatalf("migration notice was reported as no changes:\n%s", output)
	}
	for _, private := range []string{
		"private-server", "private.example", "Authorization", "private-token",
	} {
		if strings.Contains(output, private) {
			t.Fatalf("migration notice exposes %q:\n%s", private, output)
		}
	}
}

func TestMCPConfigurationPlanRendersFixedAntigravityMigrationStates(t *testing.T) {
	tests := []struct {
		state mcpconfiguration.MigrationState
		want  string
	}{
		{
			state: mcpconfiguration.MigrationEquivalentDual,
			want:  "Both Antigravity MCP locations contain equivalent configuration",
		},
		{
			state: mcpconfiguration.MigrationConflictingDual,
			want:  "Antigravity MCP locations differ",
		},
		{
			state: mcpconfiguration.MigrationInvalidLegacy,
			want:  "Legacy Antigravity MCP configuration cannot be safely inspected",
		},
	}
	for _, test := range tests {
		t.Run(string(test.state), func(t *testing.T) {
			output := renderMCPConfigurationPlan(mcpconfiguration.Plan{
				Migrations: []mcpconfiguration.MigrationAssessment{{
					ComponentID: domain.ComponentAntigravity2,
					State:       test.state,
					Reason:      "private-token",
				}},
			})
			if !strings.Contains(output, test.want) {
				t.Fatalf("migration notice is missing:\n%s", output)
			}
			if strings.Contains(output, "private-token") {
				t.Fatalf("migration notice exposes raw reason:\n%s", output)
			}
		})
	}
}

func TestMCPConfigurationPlanKeepsCanonicalOnlyStateQuiet(t *testing.T) {
	output := renderMCPConfigurationPlan(mcpconfiguration.Plan{
		Migrations: []mcpconfiguration.MigrationAssessment{{
			ComponentID: domain.ComponentAntigravity2,
			State:       mcpconfiguration.MigrationCanonicalOnly,
		}},
	})

	if !strings.Contains(output, "No MCP configuration changes") {
		t.Fatalf("canonical-only state produced unnecessary warning:\n%s", output)
	}
}
