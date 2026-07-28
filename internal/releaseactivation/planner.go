package releaseactivation

import (
	"fmt"
	"io/fs"

	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/linkownership"
	"github.com/CATWILLgh/MAINFRAME/internal/plan"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

const mainframeCLI domain.ComponentID = "mainframe-cli"

var launcherTarget = domain.Location{
	Root: domain.RootUserBin,
	Path: "mainframe",
}

func BuildPreview(
	release releasecontract.Release,
	filesystem fs.ReadLinkFS,
	roots discovery.Roots,
	registry linkownership.Registry,
) (executor.Preview, error) {
	if !releasecontract.ValidReleaseIdentity(
		release.ID,
		release.IndexSHA256,
	) {
		return executor.Preview{}, fmt.Errorf("release identity is invalid")
	}
	model, err := launcherModel(release.Model)
	if err != nil {
		return executor.Preview{}, err
	}
	launcherRegistry, err := filteredRegistry(registry)
	if err != nil {
		return executor.Preview{}, err
	}
	observed, err := discovery.DiscoverWithOwnership(
		model,
		filesystem,
		roots,
		launcherRegistry,
	)
	if err != nil {
		return executor.Preview{}, err
	}
	planned, err := plan.New(model.Catalog()).Plan(domain.PlanRequest{
		Desired: domain.DesiredState{
			Components: []domain.ComponentID{mainframeCLI},
		},
		Observed: observed,
	})
	if err != nil {
		return executor.Preview{}, err
	}
	return executor.Preview{
		Release: executor.ReleaseIdentity{
			ID:          release.ID,
			IndexSHA256: release.IndexSHA256,
		},
		Desired:       []domain.ComponentID{mainframeCLI},
		Plan:          planned,
		Configuration: configuration.PreparedPlan{},
	}, nil
}

func launcherModel(source installmodel.Model) (installmodel.Model, error) {
	var matched []installmodel.Artifact
	for _, artifact := range source.Artifacts() {
		if artifact.ComponentID == mainframeCLI {
			matched = append(matched, artifact)
		}
	}
	if len(matched) != 1 {
		return installmodel.Model{}, fmt.Errorf(
			"release must contain exactly one MAINFRAME launcher",
		)
	}
	artifact := matched[0]
	if artifact.LegacyOnly ||
		artifact.UnitID != "mainframe-cli.binary" ||
		artifact.Target != launcherTarget ||
		artifact.SourcePath != "bin/mainframe" ||
		artifact.Feature != "" ||
		len(artifact.LegacyTargetSuffixes) != 0 {
		return installmodel.Model{}, fmt.Errorf(
			"release MAINFRAME launcher contract is invalid",
		)
	}
	return installmodel.New([]installmodel.ComponentSpec{{
		ID: mainframeCLI,
		Artifacts: []installmodel.ArtifactSpec{{
			UnitID:               artifact.UnitID,
			Target:               artifact.Target,
			SourcePath:           artifact.SourcePath,
			LegacyTargetSuffixes: artifact.LegacyTargetSuffixes,
		}},
	}})
}

func filteredRegistry(
	registry linkownership.Registry,
) (linkownership.Registry, error) {
	claim, exists := registry.ClaimAt(launcherTarget)
	if !exists {
		return linkownership.New(nil)
	}
	return linkownership.New([]linkownership.Claim{claim})
}
