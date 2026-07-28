//go:build darwin || linux

package main

import (
	"errors"
	"fmt"
	"reflect"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/executor"
	"github.com/CATWILLgh/MAINFRAME/internal/hostlayout"
	"github.com/CATWILLgh/MAINFRAME/internal/linkworkspace"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecache"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func ensureReleaseApplyTarget(
	store releasecache.Store,
	request releaseApplyRequest,
) error {
	if request.Operation != releaseOperationImport {
		_, err := store.Open(request.ReleaseID, request.IndexSHA256)
		return err
	}
	inspected, err := store.InspectImport(request.SourcePath)
	if err != nil {
		return err
	}
	if inspected.ReleaseID != request.ReleaseID ||
		inspected.IndexSHA256 != request.IndexSHA256 {
		return errors.New("local release changed after review")
	}
	imported, err := store.Import(request.SourcePath)
	if err != nil {
		return err
	}
	if imported.ReleaseID != request.ReleaseID ||
		imported.IndexSHA256 != request.IndexSHA256 {
		return errors.New("local release changed while importing")
	}
	return nil
}

func inspectReleaseApplyRequest(
	environment hostlayout.Environment,
	store releasecache.Store,
	request releaseApplyRequest,
) (releaseObservation, error) {
	change := releaseChangeRequest{
		SchemaVersion: request.SchemaVersion,
		Kind:          releaseChangeKind,
		Operation:     request.Operation,
		SourcePath:    request.SourcePath,
		ReleaseID:     request.ReleaseID,
		IndexSHA256:   request.IndexSHA256,
	}
	normalized, entry, release, err := resolveReleaseReviewTarget(change, store)
	if err != nil {
		return releaseObservation{}, err
	}
	if normalized != request {
		return releaseObservation{}, errors.New(
			"local release changed after review",
		)
	}
	return observeRelease(environment, store, entry, release)
}

func executeReleaseActivation(
	environment hostlayout.Environment,
	store releasecache.Store,
	observation releaseObservation,
) (result executor.Result, err error) {
	targets := map[domain.RootID]string{
		domain.RootUserBin: observation.layout.Targets()[domain.RootUserBin],
	}
	workspace, err := linkworkspace.New(observation.entry.Path, targets)
	if err != nil {
		return executor.Result{}, fmt.Errorf("open release activation workspace: %w", err)
	}
	state, err := executor.OpenUnixState(observation.layout.State())
	if err != nil {
		return executor.Result{}, fmt.Errorf("open transaction state: %w", err)
	}
	defer func() {
		closeErr := state.Close()
		if closeErr == nil {
			return
		}
		wrapped := fmt.Errorf("close transaction state: %w", closeErr)
		if err != nil {
			err = errors.Join(err, wrapped)
			return
		}
		result.Warnings = append(result.Warnings, wrapped.Error())
	}()
	refresher := releaseActivationRefresher{
		environment: environment,
		store:       store,
		identity:    observation.preview.Release,
	}
	runner := executor.New(state, state, refresher, workspace)
	return runner.ApplyWithoutRecovery(observation.preview)
}

func (refresher releaseActivationRefresher) Refresh(
	desired []domain.ComponentID,
) (executor.Preview, error) {
	if !reflect.DeepEqual(desired, []domain.ComponentID{"mainframe-cli"}) {
		return executor.Preview{}, errors.New(
			"release activation accepts only the MAINFRAME launcher",
		)
	}
	entry, err := refresher.store.Open(
		refresher.identity.ID,
		refresher.identity.IndexSHA256,
	)
	if err != nil {
		return executor.Preview{}, err
	}
	release, err := releasecontract.Load(entry.Path)
	if err != nil {
		return executor.Preview{}, err
	}
	observation, err := observeRelease(
		refresher.environment,
		refresher.store,
		entry,
		release,
	)
	if err != nil {
		return executor.Preview{}, err
	}
	return observation.preview, nil
}
