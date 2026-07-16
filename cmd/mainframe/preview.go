package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"

	"github.com/CATWILLgh/MAINFRAME/internal/codexstate"
	"github.com/CATWILLgh/MAINFRAME/internal/configuration"
	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
	"github.com/CATWILLgh/MAINFRAME/internal/releaselayout"
	"github.com/CATWILLgh/MAINFRAME/internal/tui"
)

const releaseRootEnvironment = "MAINFRAME_RELEASE_ROOT"

func runInteractivePreview(input io.Reader, output io.Writer) error {
	service, err := buildPreviewService()
	if err != nil {
		return err
	}
	return tui.Run(input, output, &service)
}

func buildPreviewService() (lifecycle.Service, error) {
	releaseRoot, err := resolveReleaseRoot()
	if err != nil {
		return lifecycle.Service{}, err
	}
	release, err := releasecontract.Load(releaseRoot)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("load release: %w", err)
	}
	cwd, err := os.Getwd()
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("resolve working directory: %w", err)
	}
	return buildPreviewServiceFromContext(
		releaseRoot,
		release,
		cwd,
		codexstate.NewAppServerClient(),
	)
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
	layout, err := hostlayout.Resolve(hostEnvironment(), releaseRoot)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("resolve host layout: %w", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("open host namespace: %w", err)
	}
	observed, err := discovery.Discover(release.Model, namespace.Filesystem(), namespace.Roots())
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("discover current installation: %w", err)
	}
	var external configuration.ExternalObserver
	if client != nil {
		observer, err := codexstate.NewObserver(
			releaseRoot,
			cwd,
			layout.Targets(),
			release.Resources,
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
		release.Resources,
		namespace,
		external,
	)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("inspect configuration: %w", err)
	}
	service, err := lifecycle.NewWithInspection(
		release.Model,
		observed,
		configurationInspection,
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
