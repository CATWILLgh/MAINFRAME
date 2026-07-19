package application

import (
	"errors"
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/executor"
)

type RecoverySession interface {
	Recover() (executor.Result, error)
	Close() error
}

type RecoveryExecutorFactory interface {
	Open() (RecoverySession, error)
}

type RecoveryService struct {
	executors RecoveryExecutorFactory
}

func NewRecovery(executors RecoveryExecutorFactory) (RecoveryService, error) {
	if executors == nil {
		return RecoveryService{}, errors.New(
			"recovery executor factory must not be nil",
		)
	}
	return RecoveryService{executors: executors}, nil
}

func (service RecoveryService) Recover() (result executor.Result, err error) {
	session, err := service.executors.Open()
	if err != nil {
		return executor.Result{}, fmt.Errorf("open recovery executor: %w", err)
	}
	if session == nil {
		return executor.Result{}, errors.New(
			"open recovery executor: factory returned nil",
		)
	}
	defer func() {
		closeErr := session.Close()
		if closeErr == nil {
			return
		}
		wrapped := fmt.Errorf("close recovery executor: %w", closeErr)
		if err != nil {
			err = errors.Join(err, wrapped)
			return
		}
		result.Warnings = append(result.Warnings, wrapped.Error())
	}()
	return session.Recover()
}
