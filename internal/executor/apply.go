package executor

import (
	"errors"
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
)

func (executor Executor) Apply(preview Preview) (Result, error) {
	return executor.withLock(func() (Result, error) {
		if _, err := executor.recoverLocked(); err != nil {
			return Result{}, fmt.Errorf("recover unfinished transaction: %w", err)
		}
		return executor.applyFresh(preview)
	})
}

func (executor Executor) ApplyWithoutRecovery(
	preview Preview,
) (Result, error) {
	return executor.withLock(func() (Result, error) {
		journal, err := executor.store.Load()
		if err != nil {
			return Result{}, fmt.Errorf("inspect transaction state: %w", err)
		}
		if journal != nil {
			return Result{}, errors.New(
				"unfinished transaction requires recovery before review",
			)
		}
		return executor.applyFresh(preview)
	})
}

func (executor Executor) applyFresh(preview Preview) (Result, error) {
	fresh, err := executor.refresher.Refresh(
		append([]domain.ComponentID(nil), preview.Desired...),
	)
	if err != nil {
		return Result{}, fmt.Errorf("refresh preview: %w", err)
	}
	if !reflect.DeepEqual(preview, fresh) {
		return Result{}, errors.New(
			"preview changed; review the fresh plan before applying",
		)
	}
	if err := validatePreview(fresh); err != nil {
		return Result{}, err
	}
	hasMaterializations := len(fresh.Configuration.Materializations()) > 0
	materialized, err := fresh.Configuration.MaterializeSecrets(
		executor.secrets,
	)
	if err != nil {
		return Result{}, fmt.Errorf("materialize configuration secrets: %w", err)
	}
	if hasMaterializations {
		materialized, err = executor.collapseConfigurationNoOps(materialized)
		if err != nil {
			return Result{}, err
		}
	}
	fresh.Configuration = materialized
	return executor.execute(fresh)
}
