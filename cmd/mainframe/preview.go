package main

import (
	"fmt"
	"io"
	"os"
	"runtime"

	"github.com/CATWILLgh/MAINFRAME/internal/discovery"
	"github.com/CATWILLgh/MAINFRAME/internal/hostfs"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/installmanifest"
	"github.com/CATWILLgh/MAINFRAME/internal/installmodel"
	"github.com/CATWILLgh/MAINFRAME/internal/installsource"
	"github.com/CATWILLgh/MAINFRAME/internal/lifecycle"
	"github.com/CATWILLgh/MAINFRAME/internal/tui"
)

const sourceRootEnvironment = "MAINFRAME_SOURCE_ROOT"

func runInteractivePreview(input io.Reader, output io.Writer) error {
	service, err := buildPreviewService()
	if err != nil {
		return err
	}
	return tui.Run(input, output, &service)
}

func buildPreviewService() (lifecycle.Service, error) {
	model, err := installmodel.New(installmanifest.StableComponents())
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("build stable install model: %w", err)
	}
	candidates, err := sourceRootCandidates()
	if err != nil {
		return lifecycle.Service{}, err
	}
	source, err := installsource.Find(candidates, model, os.Stat, os.Lstat)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf(
			"development preview needs %s or a validated MAINFRAME working directory: %w",
			sourceRootEnvironment,
			err,
		)
	}
	layout, err := hostlayout.Resolve(hostEnvironment(), source)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("resolve host layout: %w", err)
	}
	namespace, err := hostfs.Open(layout)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("open host namespace: %w", err)
	}
	observed, err := discovery.Discover(model, namespace.Filesystem(), namespace.Roots())
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("discover current installation: %w", err)
	}
	service, err := lifecycle.New(model, observed)
	if err != nil {
		return lifecycle.Service{}, fmt.Errorf("create lifecycle preview: %w", err)
	}
	return service, nil
}

func sourceRootCandidates() ([]string, error) {
	if configured, exists := os.LookupEnv(sourceRootEnvironment); exists {
		if configured == "" {
			return nil, fmt.Errorf("%s must not be empty", sourceRootEnvironment)
		}
		return []string{configured}, nil
	}
	workingDirectory, err := os.Getwd()
	if err != nil {
		return nil, fmt.Errorf("resolve working directory: %w", err)
	}
	return []string{workingDirectory}, nil
}

func hostEnvironment() hostlayout.Environment {
	return hostlayout.Environment{
		LookupEnv:   os.LookupEnv,
		UserHomeDir: os.UserHomeDir,
		GOOS:        runtime.GOOS,
	}
}
