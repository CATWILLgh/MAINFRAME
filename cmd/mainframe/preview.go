package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostcompatibility"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpcatalog"
	"github.com/CATWILLgh/MAINFRAME/internal/mcpconfiguration"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
	"github.com/CATWILLgh/MAINFRAME/internal/releaselayout"
	"github.com/CATWILLgh/MAINFRAME/internal/tui"
)

const releaseRootEnvironment = "MAINFRAME_RELEASE_ROOT"
const repositoryStatsHTTPTimeout = 4 * time.Second

type hostApplicationDiscoverer func(string, []string) hostcompatibility.ApplicationInventory

type readOnlyReleaseSnapshot struct {
	root    string
	release releasecontract.Release
}

type interactivePlanReviewer struct {
	targets lifecycle.Service
	service application.Service
}

func (reviewer interactivePlanReviewer) Targets() []lifecycle.Target {
	return reviewer.targets.Targets()
}

func (reviewer interactivePlanReviewer) Review(
	request application.Request,
) (tui.ReviewedPlan, error) {
	reviewed, err := reviewer.service.Review(request)
	if err != nil {
		return nil, err
	}
	return reviewed, nil
}

func (reviewer interactivePlanReviewer) ApplyPlan(
	plan tui.ReviewedPlan,
) (tui.ApplyResult, error) {
	reviewed, ok := plan.(application.ReviewedPlan)
	if !ok {
		return tui.ApplyResult{}, fmt.Errorf(
			"plan was not produced by the application",
		)
	}
	result, err := reviewer.service.ApplyConfirmed(reviewed)
	if err != nil {
		return tui.ApplyResult{}, fmt.Errorf(
			"apply reviewed plan: %w",
			err,
		)
	}
	return tui.ApplyResult{
		Warnings: append([]string(nil), result.Warnings...),
	}, nil
}

func runInteractivePreview(input io.Reader, output io.Writer) error {
	reviewer, catalog, credentials, err := buildInteractiveReviewRuntime()
	if err != nil {
		return err
	}
	stats, err := mcpcatalog.NewGitHubStatsClient(
		&http.Client{Timeout: repositoryStatsHTTPTimeout},
		mcpcatalog.GitHubAPIBaseURL,
		time.Now,
	)
	if err != nil {
		return fmt.Errorf("prepare repository metadata: %w", err)
	}
	return tui.Run(input, output, reviewer, catalog, stats, credentials)
}

func buildPreviewService() (lifecycle.Service, error) {
	service, _, err := buildPreviewRuntime()
	return service, err
}

func buildPreviewRuntime() (lifecycle.Service, mcpcatalog.Catalog, error) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return lifecycle.Service{}, mcpcatalog.Catalog{}, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return lifecycle.Service{}, mcpcatalog.Catalog{}, fmt.Errorf("resolve working directory: %w", err)
	}
	service, err := buildPreviewServiceForSnapshot(snapshot, cwd)
	return service, snapshot.release.MCPCatalog, err
}

func buildInteractiveReviewRuntime() (
	interactivePlanReviewer,
	mcpcatalog.Catalog,
	tui.CredentialState,
	error,
) {
	snapshot, err := loadReadOnlyReleaseSnapshot()
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{}, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{}, fmt.Errorf(
			"resolve working directory: %w",
			err,
		)
	}
	identity := executor.ReleaseIdentity{
		ID:          snapshot.release.ID,
		IndexSHA256: snapshot.release.IndexSHA256,
	}
	service, err := buildPinnedApplyService(snapshot.root, cwd, identity)
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{}, err
	}
	recovery, err := service.Recover()
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{},
			fmt.Errorf("recover unfinished operation before review: %w", err)
	}
	credentials, err := loadCredentialRuntime(snapshot.root, snapshot.release)
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{}, err
	}
	targets, err := buildPreviewServiceForSnapshot(snapshot, cwd)
	if err != nil {
		return interactivePlanReviewer{}, mcpcatalog.Catalog{}, tui.CredentialState{}, err
	}
	return interactivePlanReviewer{
			targets: targets,
			service: service,
		}, snapshot.release.MCPCatalog, tui.CredentialState{
			Definitions: credentials.definitions,
			Instances:   credentials.snapshot.Instances(),
			Recovered:   recovery.Recovered,
			Warnings:    append([]string(nil), recovery.Warnings...),
		}, nil
}

func buildPreviewServiceForSnapshot(
	snapshot readOnlyReleaseSnapshot,
	cwd string,
) (lifecycle.Service, error) {
	return buildPreviewServiceFromContextWithHostDiscovery(
		snapshot.root,
		snapshot.release,
		cwd,
		codexstate.NewAppServerClient(),
		hostcompatibility.DiscoverApplications,
	)
}

func loadReadOnlyReleaseSnapshot() (readOnlyReleaseSnapshot, error) {
	releaseRoot, err := resolveReleaseRoot()
	if err != nil {
		return readOnlyReleaseSnapshot{}, err
	}
	release, err := releasecontract.Load(releaseRoot)
	if err != nil {
		return readOnlyReleaseSnapshot{}, fmt.Errorf("load release: %w", err)
	}
	return readOnlyReleaseSnapshot{root: releaseRoot, release: release}, nil
}

func buildPreviewServiceFrom(
	releaseRoot string,
	release releasecontract.Release,
) (lifecycle.Service, error) {
	return buildPreviewServiceFromContext(releaseRoot, release, "", nil)
}

func buildPreviewServiceFromContext(
	releaseRoot string,
	release releasecontract.Release,
	cwd string,
	client codexstate.Client,
) (lifecycle.Service, error) {
	return buildPreviewServiceFromContextWithHostDiscovery(
		releaseRoot,
		release,
		cwd,
		client,
		hostcompatibility.DiscoverApplications,
	)
}

func buildPreviewServiceFromContextWithHostDiscovery(
	releaseRoot string,
	release releasecontract.Release,
	cwd string,
	client codexstate.Client,
	discover hostApplicationDiscoverer,
) (lifecycle.Service, error) {
	return buildPreviewServiceFromContextWithObservation(
		releaseRoot,
		release,
		cwd,
		client,
		diagnosticsObservationScope{},
		discover,
	)
}

func buildPreviewServiceFromContextWithObservation(
	releaseRoot string,
	release releasecontract.Release,
	cwd string,
	client codexstate.Client,
	scope diagnosticsObservationScope,
	discover hostApplicationDiscoverer,
) (lifecycle.Service, error) {
	environment := hostEnvironment()
	layout, err := hostlayout.Resolve(environment, releaseRoot)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("resolve host layout: %w", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("open host namespace: %w", err)
	}
	inspectionHost := newInspectionCache(namespace)
	ownership, err := executor.ReadUnixOwnership(layout.State())
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("read installation ownership: %w", err)
	}
	observed, err := discovery.DiscoverWithOwnership(
		release.Model,
		namespace.Filesystem(),
		namespace.Roots(),
		ownership,
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("discover current installation: %w", err)
	}
	service, err := buildInspectedService(
		releaseRoot, release, cwd, client, layout, inspectionHost, observed, scope,
	)
	if err != nil {
		return lifecycle.Service{}, err
	}
	if len(release.HostRequirements) == 0 {
		return service, nil
	}
	if discover == nil {
		return lifecycle.Service{}, fmt.Errorf("host application discoverer must not be nil")
	}
	targets := layout.Targets()
	inventory := discover(environment.GOOS, []string{
		"/Applications",
		filepath.Join(targets[domain.RootHome], "Applications"),
	})
	service, err = service.WithHostCompatibility(
		hostcompatibility.Evaluate(release.HostRequirements, inventory),
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("apply host compatibility: %w", err)
	}
	return service, nil
}

func buildInspectedService(
	releaseRoot string,
	release releasecontract.Release,
	cwd string,
	client codexstate.Client,
	layout hostlayout.Layout,
	inspectionHost configuration.Host,
	observed domain.ObservedState,
	scope diagnosticsObservationScope,
) (lifecycle.Service, error) {
	resources := resourcesForDiagnosticsObservation(
		release.Resources,
		scope,
		observed,
	)
	var external configuration.ExternalObserver
	if client != nil {
		observer, err := codexstate.NewObserver(
			releaseRoot,
			cwd,
			layout.Targets(),
			resources,
			client,
		)
		if err != nil {
			return lifecycle.Service{}, fmt.Errorf(
				"prepare Codex state observer: %w",
				err,
			)
		}
		external = observer
	}
	configurationInspection, err := configuration.InspectWithExternal(
		resources,
		inspectionHost,
		external,
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("inspect configuration: %w", err)
	}
	mcpInspection, err := mcpconfiguration.Inspect(
		release.MCPProjections,
		release.MCPCatalog,
		inspectionHost,
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("inspect MCP configuration: %w", err)
	}
	service, err := lifecycle.NewWithInspections(
		release.Model,
		observed,
		configurationInspection,
		mcpInspection,
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("create lifecycle preview: %w", err)
	}
	return service, nil
}

func resolveReleaseRoot() (string, error) {
	explicit, exists := os.LookupEnv(releaseRootEnvironment)
	root, err := releaselayout.Resolve(
		explicit,
		exists,
		os.Executable,
		filepath.EvalSymlinks,
	)
	if err != nil {
		return "", fmt.Errorf("resolve release root: %w", err)
	}
	return root, nil
}

func hostEnvironment() hostlayout.Environment {
	return hostlayout.Environment{
		LookupEnv:   os.LookupEnv,
		UserHomeDir: os.UserHomeDir,
		GOOS:        runtime.GOOS,
	}
}
