package installmanifest

import (
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
)

// StableComponents returns artifacts whose names do not depend on generated collection contents.
func StableComponents() []installmodel.ComponentSpec {
	return []installmodel.ComponentSpec{
		{
			ID: domain.ComponentClaudeCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootClaudeConfig, "CLAUDE.md", "dist/claude-code/CLAUDE.md", "export/CLAUDE.md"),
				desired(domain.RootClaudeConfig, "settings.json", "dist/claude-code/settings.json", "export/settings.json"),
				desired(domain.RootClaudeConfig, "skills/mainframe", "dist/claude-code/plugin", "plugin-dist"),
				desired(domain.RootUserBin, "secret", "dist/claude-code/scripts/secret", "export/scripts/secret"),
			},
			LegacyArtifacts: claudeLegacyArtifacts(),
		},
		{
			ID: domain.ComponentCodex,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootCodexConfig, "AGENTS.md", "dist/codex/AGENTS.md"),
			},
		},
		{
			ID: domain.ComponentOpenCode,
			Artifacts: []installmodel.ArtifactSpec{
				desired(domain.RootOpenCodeConfig, "AGENTS.md", "dist/opencode/AGENTS.md", "export/AGENTS.md"),
			},
		},
		{
			ID:           domain.ComponentCodexGates,
			Dependencies: []domain.ComponentID{domain.ComponentSharedGateDetectors},
		},
		{ID: domain.ComponentSharedGateDetectors},
	}
}

func desired(root domain.RootID, target, source domain.ArtifactPath, historical ...domain.ArtifactPath) installmodel.ArtifactSpec {
	suffixes := make([]domain.ArtifactPath, 1, len(historical)+1)
	suffixes[0] = source
	suffixes = append(suffixes, historical...)
	return installmodel.ArtifactSpec{
		Target: domain.Location{
			Root: root,
			Path: target,
		},
		SourcePath:           source,
		LegacyTargetSuffixes: suffixes,
	}
}

func claudeLegacyArtifacts() []installmodel.LegacyArtifactSpec {
	targets := []domain.ArtifactPath{
		"skills/code-audit",
		"skills/curl-requests",
		"skills/git-conventional-commits-ru",
		"skills/nestjs-backend-patterns",
		"skills/no-suppression-markers",
		"skills/ops-app-server-safety",
		"skills/python-backend-patterns",
		"skills/react-frontend-patterns",
		"skills/secrets-handling",
		"skills/severity-calibration",
		"skills/shadcn",
		"skills/surface-ticket",
		"skills/task-workflow",
		"skills/testing-strategy",
		"agents/nestjs-backend-engineer.md",
		"agents/python-backend-engineer.md",
		"agents/react-frontend-engineer.md",
		"agents/web-search.md",
		"hooks/bash-pattern-reminder.py",
		"hooks/comment-discipline-reminder.py",
		"hooks/frontend-dead-code.py",
		"hooks/frontend-fsd-gate.py",
		"hooks/nodejs-deps-audit.py",
		"hooks/nodejs-security-scan.py",
		"hooks/nodejs-security-stop-gate.py",
		"hooks/path-validation.py",
		"hooks/python-deps-audit.py",
		"hooks/python-security-scan.py",
		"hooks/python-security-stop-gate.py",
		"hooks/scan-suppression-markers.py",
		"hooks/stop-gate-suppression-markers.py",
		"hooks/rules",
	}
	artifacts := make([]installmodel.LegacyArtifactSpec, 0, len(targets))
	for _, target := range targets {
		artifacts = append(artifacts, installmodel.LegacyArtifactSpec{
			Target: domain.Location{
				Root: domain.RootClaudeConfig,
				Path: target,
			},
			TargetSuffixes: []domain.ArtifactPath{"export/" + target},
		})
	}
	return artifacts
}
