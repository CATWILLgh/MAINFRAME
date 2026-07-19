package main

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/application"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
)

type productionRecoveryExecutorFactory struct {
	layout hostlayout.RecoveryLayout
}

func (factory productionRecoveryExecutorFactory) Open() (
	application.RecoverySession,
	error,
) {
	workspace, err := linkworkspace.NewRecovery(factory.layout.Targets())
	if err != nil {
		return nil, fmt.Errorf("open recovery workspace: %w", err)
	}
	state, err := executor.OpenUnixState(factory.layout.State())
	if err != nil {
		return nil, fmt.Errorf("open transaction state: %w", err)
	}
	runner := executor.NewWithConfiguration(
		state,
		state,
		nil,
		workspace,
		workspace,
	)
	return &productionExecutorSession{executor: runner, state: state}, nil
}

func newProductionRecoveryExecutorFactory() (
	productionRecoveryExecutorFactory,
	error,
) {
	layout, err := hostlayout.ResolveRecovery(hostEnvironment())
	if err != nil {
		return productionRecoveryExecutorFactory{}, fmt.Errorf(
			"resolve recovery layout: %w",
			err,
		)
	}
	return productionRecoveryExecutorFactory{layout: layout}, nil
}

func buildRecoveryService() (application.RecoveryService, error) {
	factory, err := newProductionRecoveryExecutorFactory()
	if err != nil {
		return application.RecoveryService{}, err
	}
	service, err := application.NewRecovery(factory)
	if err != nil {
		return application.RecoveryService{}, fmt.Errorf(
			"build recovery service: %w",
			err,
		)
	}
	return service, nil
}
